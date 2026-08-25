#!/usr/bin/env bash
# Checks a commit subject against the shape CLAUDE.md states, which prek cannot
# see because the message never reaches a file its hooks are given. A message
# passed any way other than a quoted -m is left to prek and to review.
set -euo pipefail

types='feat|fix|refactor|perf|docs|test|chore|build|ci|style|revert'
scopes='machine|fit|model|dialect|profile|binding|lmstudio|claude-code|opencode|cli|ci|deps'
limit=72

payload=$(cat)
command=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')

[[ $command == *"git commit"* ]] || exit 0

subject=$(printf '%s' "$command" |
	sed -n -e 's/.*-m[[:space:]]*"\([^"]*\)".*/\1/p' -e "s/.*-m[[:space:]]*'\([^']*\)'.*/\1/p" |
	head -1)

[[ -n $subject ]] || exit 0

pattern="^($types)(\((($scopes))\))?!?: .+"

if [[ ! $subject =~ $pattern ]]; then
	printf 'Subject is not <type>(<scope>): <summary>.\n' >&2
	printf 'Types: %s\n' "${types//|/, }" >&2
	printf 'Scopes: %s\n' "${scopes//|/, }" >&2
	printf 'Got: %s\n' "$subject" >&2
	exit 2
fi

if ((${#subject} > limit)); then
	printf 'Subject is %d characters, past %d: %s\n' "${#subject}" "$limit" "$subject" >&2
	exit 2
fi

if [[ $subject == *. ]]; then
	printf 'Subject ends in a period: %s\n' "$subject" >&2
	exit 2
fi
