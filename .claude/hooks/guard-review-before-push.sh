#!/usr/bin/env bash
# Stops a push or a pull request going out before the deeper review CLAUDE.md
# asks for has been run on the work. The rule is written down and was still
# missed, because the skill that implements a change ends at a different
# review and nothing reads the project's own rule at the moment of pushing.
#
# What it looks for is an agent actually being launched, not the toolkit being
# mentioned: a conversation about reviewing would otherwise satisfy the guard
# it is discussing.
#
# It allows what it cannot check. An unreadable transcript means the harness
# changed shape, and a guard that cannot see is a guard that should not brick
# every push on the machine — the rule it enforces is a habit, not a
# permission.
set -euo pipefail

payload=$(cat)
command=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')

case $command in
*"git push"* | *"gh pr create"*) ;;
*) exit 0 ;;
esac

[[ ${OFFGRID_SKIP_PR_REVIEW:-} == 1 ]] && exit 0

transcript=$(printf '%s' "$payload" | jq -r '.transcript_path // empty')
[[ -n $transcript && -r $transcript ]] || exit 0

# The shapes a launched agent and an invoked skill take in the transcript.
# Both carry the toolkit's name inside a JSON field, which prose about a
# review cannot reproduce.
#
# Assembled here rather than written out, because the transcript records this
# file being read and written: spelled in full, the guard would be satisfied
# by anyone who had opened it.
toolkit='pr-review-toolkit:'
launched='"subagent_type":"'$toolkit
invoked='"skill":"'$toolkit

grep -qF -e "$launched" -e "$invoked" "$transcript" && exit 0

cat >&2 <<'MESSAGE'
CLAUDE.md asks for /pr-review-toolkit:review-pr before pushing, and this
session has not run it.

Always code-reviewer and silent-failure-hunter; add pr-test-analyzer when
tests changed, type-design-analyzer when a type was added, comment-analyzer
when a comment claims something about hardware or a runtime.

Run it, act on what it finds, then push. If this push does not want one — a
docs branch, a re-push of reviewed work — say so out loud and run it again
with OFFGRID_SKIP_PR_REVIEW=1.
MESSAGE
exit 2
