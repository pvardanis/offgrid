#!/usr/bin/env bash
# Holds the 200-line limit as a ratchet against the committed file: one already
# past it is left alone until an edit makes it longer, so the files that are
# long today do not drown out the one that just crossed.
set -euo pipefail

limit=200

# shellcheck source=SCRIPTDIR/lib/edited-file.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/edited-file.sh"

[[ $path == *.py && -f $path ]] || exit 0

lines() { tr -dc '\n' | wc -c | tr -d ' '; }

after=$(lines <"$path")

# A file the last commit does not hold reads as nothing, so it is measured
# against zero and any length past the limit is its own doing.
before=$(git show "HEAD:$relative" 2>/dev/null | lines || true)

if ((after > limit && after > before)); then
	printf '%s is %d lines, past the %d-line limit (was %d). Split it by domain.\n' \
		"$relative" "$after" "$limit" "$before" >&2
	exit 2
fi
