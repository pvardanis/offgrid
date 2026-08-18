# Names the file a hook payload touched, as a path this repository holds, and
# ends the calling hook when the edit is to anything else. Sourced, so a caller
# is handed `path` and `relative` with nothing left to check.
#
# The payload spells a path the way the caller was given it and git spells the
# repository root with every symlink resolved, so the two are compared only
# after the payload's path has been resolved the same way. A file that does not
# exist yet resolves through the deepest directory that does.

# shellcheck shell=bash
# shellcheck disable=SC2034  # `path` and `relative` are read by the sourcing hook.

resolve_path() {
	local target=$1 directory
	local missing=''

	directory=$(dirname "$target")

	while [[ ! -d $directory && $directory == */* ]]; do
		missing=$(basename "$directory")/$missing
		directory=$(dirname "$directory")
	done

	[[ -d $directory ]] || return 1
	directory=$(cd "$directory" && pwd -P) || return 1

	printf '%s/%s%s' "$directory" "$missing" "$(basename "$target")"
}

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

path=$(jq -r '.tool_input.file_path // empty')
[[ -n $path ]] || exit 0

path=$(resolve_path "$path") || exit 0
[[ $path == "$root"/* ]] || exit 0

relative=${path#"$root"/}
