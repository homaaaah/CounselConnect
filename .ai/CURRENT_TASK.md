# CounselConnect — Current Task

**Status:** ACTIVE

## Objective

Publish the whole project as an initial backup to a new GitHub repository with zero secrets and zero applicant data in the commit.

## Scope

**In:**
- Sanitize `backend/.env.example` (it currently duplicates the real `.env`, including the MySQL password, Gmail SMTP app password, and dev admin key).
- Extend root `.gitignore` (`.opencode/`, `.kilocode/`, `desktop.ini`).
- Initialize git on `main`, create the initial commit, connect the GitHub remote, push, and record completion (second commit).

**Out:**
- Any application behavior change, refactors, renames, CI, or docs-contract edits.
- Moving the project out of OneDrive; GitHub account/repo settings beyond this push.

## Acceptance criteria

1. `backend/.env`, `frontend/.env`, `backend/var/**` (applicant CORs), `backend/.venv/**`, `frontend/node_modules/**` are untracked (verified with `git check-ignore`).
2. A secret-pattern scan (DB password, Gmail address, app password, dev admin key) over files git would track returns no matches.
3. Both `.env.example` files are tracked with placeholder values only.
4. Initial commit is pushed to `origin/main`; `git ls-remote origin main` shows the ref.

## Verification (planned)

- `git status --short` + `git ls-files` full staged-tree review.
- `git check-ignore` on every sensitive path.
- rg secret scan excluding ignored trees.
- Push output + `git ls-remote origin main`.

## Human decisions needed (asked this session)

- Repo visibility (private recommended).
- GitHub repo URL (user creates the empty repo on github.com; gh CLI is not installed).
- Commit author name (git `user.name` is currently unset locally).
