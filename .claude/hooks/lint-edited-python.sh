#!/usr/bin/env bash
# Lints and type-checks a Python file the moment it is written, so a mistake is
# answered while the change is still in hand rather than at the commit prek
# gates. Nothing is fixed here: prek owns the rewriting, and a file rewritten
# behind the agent that just wrote it is a file the agent no longer knows.
set -euo pipefail

# shellcheck source=SCRIPTDIR/lib/edited-file.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/edited-file.sh"

[[ $path == *.py && -f $path ]] || exit 0

if ! report=$(uv run ruff check "$path" 2>&1); then
	printf 'ruff on %s:\n%s\n' "$relative" "$report" >&2
	exit 2
fi

if ! report=$(uv run ty check "$path" 2>&1); then
	printf 'ty on %s:\n%s\n' "$relative" "$report" >&2
	exit 2
fi
