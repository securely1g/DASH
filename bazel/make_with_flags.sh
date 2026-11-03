# Sourced by rules_foreign_cc's public tool_prefix before starting Make.
# Keep ordered flags out of recursive Make's MAKEFLAGS export. A GCC driver
# response file expands at the original position, preserving order relative
# to CFLAGS/CXXFLAGS too. DASH's compile and link commands remain separate.
(
    set -eu
    cppflags_file="$PWD/.bazel-dash-cppflags.rsp"
    printf '%s\n' "${CPPFLAGS:-}" > "$cppflags_file"
    export CPPFLAGS="@$cppflags_file"
    "$@"
)
