# Git hygiene

Reference for branch, hook, and commit conventions. Everything here is either
already applied in the repository or enabled with one `git config` call per
clone.

## Branches

`main` is the integration branch and is merge-only: a change lands through a
pull request, never by a direct push. Work happens on `agentN/<topic>` branches.

Clean-up rules used to prune the branch set:

- a branch whose tip is an ancestor of `main` is merged and can be deleted;
- a branch with commits not in `main` is kept until its pull request is settled.

```
git fetch --all --prune
for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin/); do
    git merge-base --is-ancestor "$b" origin/main && echo "merged: $b"
done
```

## .gitignore

The ignore file covers the environments and tools in use: `.venv/`,
`__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `build/`,
`dist/`, and editor droppings, plus the agent scratch directories `.agent-cache/`
and `.openhands/`. The Slidev build output under `presentation/`
(`node_modules/`, `dist/`, `.vite-cache/`) is ignored too. Capture files
(`*.pcap`, `*.pcapng`) are ignored by default, with the fixtures, corpus, and
reference exports re-included explicitly.

Large generated binaries stay out of history: `presentation/video.mp4` is
ignored and rebuilt from `presentation/VIDEO.md`. The committed artefacts
(`slides.pdf`, `screencast.mp4`) are intentional deliverables.

## .gitattributes

Binary assets are marked `binary` so Git never attempts a text diff or a
line-wise merge on them, and `*.pcap`/`*.pcapng` are data rather than text.
Build output collapses to a one-line summary. Text files are normalized to LF
on checkout.

## Pre-commit hook

`.githooks/pre-commit` lints the staged Python files with the starter ruleset and
runs the fast protocol and hypothesis tests. Enable it once per clone:

```
git config core.hooksPath .githooks
```

Bypass a single commit with `git commit --no-verify`. The hook skips cleanly if
no Python with `ruff` is available, so it never blocks a machine without the dev
extras.

## Commit messages

Commits follow Conventional Commits, in English, with a subject of 72
characters or fewer. Enable the template once per clone:

```
git config commit.template .gitmessage
```

Types in use: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `style`,
`perf`, `build`, `ci`, `revert`. Merge commits and a small number of early
history entries predate the convention and are left untouched; rewriting
history is out of scope.

## Secrets

`git log --all -p` finds no access token, key, or password. The strings
`ghp_`/`github_pat_` appear only inside this audit's own documentation, as the
search pattern, never as a value. `.env.example` carries placeholders only;
`.env` is ignored. The runtime token is read from the `GITHUB_TOKEN` environment
variable and is never written into a file.

## CHANGELOG

`CHANGELOG.md` is written from `git log`, grouped by iteration, with the short
hashes of the commits that made each change.

## .mailmap

`.mailmap` folds the automated commit identity into the maintainer identity so
`git shortlog` and `git log` attribute every commit to the person.
