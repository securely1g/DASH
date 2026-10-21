# DASH BMv2 source build with Bazel

The Bazel path compiles the existing BMv2 P4 pipeline with the declared p4c
execution tool, runs the existing SAI generator in a private source tree, and
invokes the original SAI metadata and DASH library Make targets through
`rules_foreign_cc`. It does not invoke Debian packaging. Existing Docker/Make
builds remain available with their original source files.

Public targets:

| Target | Output |
| --- | --- |
| `//:runtime` | Stripped `libsai.so`, `libdashsaimetadata.so`, and four generated `/etc/dash` pipeline files |
| `//:runtime.debug_symbols` | Matching detached symbols under `/usr/lib/debug/.build-id` |
| `//:sdk` | Installed public headers and a linkable DASH SAI library for C++ consumers |
| `//bazel:runtime_test` | Installed SDK API call, pipeline validation, dependency closure, debug IDs/checksums, and GDB source-line lookup |

Native Trixie AMD64 and ARM64 are the validation configurations. Cross-compiling
the source generator/metadata executables is not supported. Set both platforms
for ARM64:

```sh
bazel test //bazel:runtime_test \
  --platforms=@sonic_build_infra//platforms:aarch64_trixie \
  --host_platform=@sonic_build_infra//platforms:aarch64_trixie
```

AMD64 is the default. Bazel 8.5.1, compiler/tool dependencies and generator wheels
are declared. The tests use the CI userspace's `readelf`, `objcopy` and GDB to
inspect outputs. Compilation uses the declared shared toolchain and target
dependencies; target dependency imports do not count as source builds of those
external libraries.

`requirements_lock.txt` is checked-in Python dependency input.
`MODULE.bazel.lock` is ignored generated resolution state retained in CI evidence.
`-g` and `--strip=never` preserve build-time symbols; shared `sonic_deploy_tar`
rules split the deployed runtime and debug TARs from the same linked ELF.

The draft CI currently freezes `codex/p4-source-validation` from the shared
registry, replacing its normal `main` endpoint for the run. That temporary
branch combines the separate PI, p4c and shared-tool prerequisites. Remove this
draft substitution once they land; the PR cannot become Ready before the native
matrix passes against landed registry entries. Workflow artifacts contain both
TARs, checksums, source/registry revisions, test results and the generated lock.

The draft prerequisites are:

| Module | Prerequisite |
| --- | --- |
| `rules_distroless@0.9.4.sonic.9` | [Complete C++ header imports, registry #91](https://github.com/securely1g/sonic-bazel-registry/pull/91) |
| `p4lang-pi@0.1.3.sonic.1` | [PI source producer, registry #88](https://github.com/securely1g/sonic-bazel-registry/pull/88) |
| `p4c@1.2.4.2.sonic.1` | [P4C source producer, registry #86](https://github.com/securely1g/sonic-bazel-registry/pull/86) |
| `sonic-build-infra@0.0.18-15f89e5b1e8fa72301ab52ff3655a5abdc059822` | [Shared tools #53](https://github.com/securely1g/sonic-build-infra/pull/53), [GCC/Libtool adapter #54](https://github.com/securely1g/sonic-build-infra/pull/54), [registry #87](https://github.com/securely1g/sonic-bazel-registry/pull/87) |

The two `Native source and TARs` checks are required on `main`. Their successful source builds and installed runtime/debug tests are merge gates; a completed analysis or a queued workflow does not satisfy them.
