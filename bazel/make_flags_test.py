"""Exercise the original recursive Make adapter with ordered GCC flags."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def main():
    adapter, frontend = [Path(value).resolve() for value in sys.argv[1:]]
    tools = {name: shutil.which(name) for name in ("bash", "make", "gcc", "g++")}
    assert all(tools.values()), tools
    with tempfile.TemporaryDirectory(dir=os.environ.get("TEST_TMPDIR")) as temporary:
        root = Path(temporary)
        generated = root / "generated_sources"
        metadata = generated / "dash-pipeline/SAI/SAI/meta"
        library = generated / "dash-pipeline/SAI/lib"
        metadata.mkdir(parents=True)
        library.mkdir(parents=True)
        shutil.copyfile(frontend, generated / "Makefile")
        for name, value in (("first", 13), ("second", 29)):
            (root / name).mkdir()
            (root / name / "selected.h").write_text(f"#define SELECTED {value}\n")
        (root / "quoted include").mkdir()
        (root / "quoted include/quoted_path.h").write_text("#define SPACE_HEADER 31\n")
        (root / "compiler-system").mkdir()
        (root / "compiler-system/selected.h").write_text("#define SELECTED 47\n")
        program = (
            "#include <selected.h>\n#include <quoted_path.h>\n"
            "static const char *text = STRING;\n"
            "int main(void) { return VALUE + SELECTED != 24 || SPACE_HEADER != 31 || "
            "text[0] != 'q' || text[6] != ' ' || text[7] != 'v'; }\n"
        )
        (metadata / "unit.c").write_text(program)
        (library / "unit.cc").write_text(program)
        # Use the real frontend's two recursive calls. The metadata call carries
        # link flags in CXX (used only to link the C object); the library call
        # carries GXX_FLAGS and LDFLAGS as
        # command-line overrides, which GNU Make also exports in MAKEFLAGS.
        (metadata / "Makefile").write_text(
            ".PHONY: libsaimetadata.so\nlibsaimetadata.so:\n"
            "\t$(CC) $(CFLAGS) -c unit.c -o unit.o\n"
            "\t$(CXX) unit.o -o program\n"
        )
        (library / "Makefile").write_text(
            ".PHONY: all\nall:\n"
            "\t$(file >makeflags.txt,$(MAKEFLAGS))\n"
            "\t$(file >linkflags.txt,$(LDFLAGS))\n"
            "\t$(file >libs.txt,$(LIBS))\n"
            "\t$(CXX) $(GXX_FLAGS) -c unit.cc -o unit.o\n"
            "\t$(CXX) unit.o $(LDFLAGS) -o program\n"
        )
        common = shlex.join([
            "-DVALUE=1", "-UVALUE", "-DVALUE=7", '-DSTRING="quoted value"',
            "-isystem", str(root / "first"), "-isystem", str(root / "second"),
            "-I" + str(root / "quoted include"), "-Wno-unused-parameter",
        ])
        large_cpp = " ".join(f"-I/nonexistent/{i}/" + "x" * 180 for i in range(430)) + " " + common
        large_link = " ".join(f"-L/nonexistent/{i}/" + "y" * 180 for i in range(330)) + " -Wl,--as-needed"
        # Each original variable fits execve, but their recursive Make export
        # exceeds the per-string bound seen in the actual DASH failure.
        assert len(large_cpp) < 131072 and len(large_link) < 131072
        assert len(large_cpp) + len(large_link) > 131072

        def run(cppflags, ldflags, prefix):
            assignments = {
                "CC": tools["gcc"], "CXX": tools["g++"], "CPPFLAGS": cppflags,
                "CFLAGS": "-O2 -g -frandom-seed=fixture -UVALUE -DVALUE=11 -isystem " + shlex.quote(str(root / "compiler-system")),
                "CXXFLAGS": "-O2 -g -frandom-seed=fixture -UVALUE -DVALUE=11 -isystem " + shlex.quote(str(root / "compiler-system")),
                "LDFLAGS": ldflags, "LIBS": "",
            }
            command = " ".join(key + "=" + shlex.quote(value) for key, value in assignments.items())
            if prefix:
                command += " source " + shlex.quote(str(adapter))
            command += " " + shlex.join([tools["make"], "--no-print-directory", "-f", "generated_sources/Makefile", "all"])
            script = root / "invoke.sh"
            script.write_text(command + "\n")
            return subprocess.run([tools["bash"], script], cwd=root, capture_output=True, text=True)

        # Prove the exact recursive override/export failure independently of
        # GCC: a trivial child cannot start when MAKEFLAGS exceeds the limit.
        probe = root / "probe"
        probe.mkdir()
        (probe / "Makefile").write_text(
            "all:\n\t$(file >makeflags.txt,$(MAKEFLAGS))\n\t@/bin/true\n"
        )
        old = subprocess.run(
            [tools["make"], "--no-print-directory", "-C", str(probe),
             "GXX_FLAGS=" + large_cpp, "LDFLAGS=" + large_link],
            capture_output=True, text=True,
        )
        assert len((probe / "makeflags.txt").read_bytes()) > 131072
        assert old.returncode != 0 and "Argument list too long" in old.stderr, old.stderr

        # A preprocessor-only response would reorder CPPFLAGS after native
        # compiler include options. Keep this concrete negative control: the
        # first header must win across the CPPFLAGS/CFLAGS boundary.
        (root / "order.c").write_text("#include <selected.h>\nSELECTED\n")
        (root / "order.rsp").write_text("-isystem " + str(root / "first") + "\n")
        def selected(flags):
            return subprocess.check_output([tools["gcc"], "-E", "-P", *flags,
                                            "-isystem", str(root / "compiler-system"),
                                            str(root / "order.c")], text=True).strip()
        assert selected(["-isystem", str(root / "first")]) == "13"
        assert selected(["-Wp,@" + str(root / "order.rsp")]) == "47"
        assert selected(["@" + str(root / "order.rsp")]) == "13"

        hashes = []
        for cppflags, ldflags in ((common, "-Wl,--as-needed"), (large_cpp, large_link)):
            accepted = run(cppflags, ldflags, True)
            assert accepted.returncode == 0, accepted.stdout + accepted.stderr
            assert (root / ".bazel-dash-cppflags.rsp").read_text() == cppflags + "\n"
            installed = root / "dash-pipeline/SAI"
            assert (installed / "lib/linkflags.txt").read_text() == ldflags + " -Wl,-z,defs\n"
            assert (installed / "lib/libs.txt").read_text().strip() == "-lpiprotogrpc -lpiprotobuf -lgrpc++ -lgrpc -lprotobuf -lgpr -labsl_synchronization"
            assert len((installed / "lib/makeflags.txt").read_bytes()) < 131072
            row = {}
            for name in ("SAI/meta/program", "lib/program"):
                binary = installed / name
                subprocess.run([binary], check=True)
                row[name] = hashlib.sha256(binary.read_bytes()).hexdigest()
            hashes.append(row)
        assert hashes[0] == hashes[1], hashes
        for prefix in (False, True):
            rejected = run("-fdefinitely-invalid-dash-option", "", prefix)
            assert rejected.returncode != 0 and "unrecognized command-line option" in rejected.stderr, rejected.stderr
        print(json.dumps({"status": "passed", "cppflags_bytes": len(large_cpp), "ldflags_bytes": len(large_link), "binaries": hashes[0]}, sort_keys=True))


if __name__ == "__main__":
    main()
