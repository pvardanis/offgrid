#!/usr/bin/env bash
# Refuses an edit to this repository while main is checked out, so work starts
# on a branch rather than being found on main once it is already written.
set -euo pipefail

# shellcheck source=SCRIPTDIR/lib/edited-file.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/edited-file.sh"

branch=$(git branch --show-current 2>/dev/null || true)

if [[ $branch == "main" ]]; then
	printf 'main is checked out, and %s is in this repository.\n' "$relative" >&2
	printf 'Start a branch first: wt switch <branch>.\n' >&2
	exit 2
fi
