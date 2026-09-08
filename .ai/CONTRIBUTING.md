# Contributing to CounselConnect

This guide defines the team's Git and GitHub workflow. Its purpose is to keep `main` stable, isolate unfinished work, and ensure that human-reviewed changes enter the shared codebase.

## Branch structure

`main` is the latest reviewed and working version. Do not work or push directly on it.

Create one short-lived branch for each task:

| Work area | Branch pattern | Example |
| --- | --- | --- |
| Frontend | `frontend/<task-name>` | `frontend/student-login` |
| Backend | `backend/<task-name>` | `backend/session-api` |
| Database | `database/<task-name>` | `database/user-sessions` |
| Documentation | `docs/<task-name>` | `docs/update-authentication` |
| Bug fix | `fix/<task-name>` | `fix/appointment-validation` |

Do not create permanent `frontend` or `backend` branches. They can drift apart and make integration harder.

## Before starting a task

Make sure unfinished local work has already been committed to its own branch. Then update `main`:

```bash
git switch main
git pull origin main
```

Create the task branch:

```bash
git switch -c frontend/student-login
```

Replace the example with the correct work area and a short, descriptive task name.

## Work within the assigned scope

| Branch prefix | Normal write scope |
| --- | --- |
| `frontend/` | `frontend/**` |
| `backend/` | `backend/**` and backend tests |
| `database/` | `db/**`, migrations, approved backend models, and related tests |
| `docs/` | `.ai/**`, `contracts/**`, `docs/**`, and approved root Markdown files |
| `fix/` | Only the files required by the specific bug |

Reading other folders for context is allowed. If a task requires changes outside the assigned scope, coordinate with the responsible member instead of allowing an agentic AI to change unrelated areas automatically.

## Review changes before committing

Run:

```bash
git status
git diff
git diff --name-only
```

Confirm that:

- only assigned files were changed;
- existing work was not unintentionally removed;
- `.env` files, passwords, API keys, uploaded student files, and personal information are not included;
- generated files are included only when the project requires them;
- implementation follows the applicable files in `.ai/`, `contracts/`, and `docs/`.

## Commit the task

Add specific files or folders when possible:

```bash
git add frontend/src/features/auth
git commit -m "Add student login interface"
```

Do not use `git add .` without first reviewing every listed change.

## Synchronize with `main`

Before opening a pull request:

```bash
git fetch origin
git merge origin/main
```

If a conflict occurs:

1. Do not force-push or delete files blindly.
2. Coordinate with the member who changed the same file.
3. Resolve the conflict using VS Code's Merge Editor.
4. Test the combined result.
5. Add and commit the resolved files.

## Push and open a pull request

Push the task branch:

```bash
git push -u origin frontend/student-login
```

On GitHub, open a pull request with:

- base branch: `main`;
- compare branch: the task branch;
- a short explanation of what was implemented;
- the folders or important files changed;
- how the work was tested;
- any remaining frontend, backend, database, or documentation dependency.

## Review and merge

At least one other member should review the pull request. The reviewer checks:

- the **Files changed** section;
- unrelated or unexpectedly deleted code;
- relevant test results;
- consistency with API and database contracts;
- exposed secrets or sensitive information.

After approval, use **Squash and merge**, then delete the remote task branch.

## Update after merging

```bash
git switch main
git pull origin main
git branch -d frontend/student-login
```

Create a new branch for the next task. Do not reuse a completed branch.

## Rules for agentic AI

- The AI may read the entire repository but may modify only paths authorized by the task.
- The AI must not begin implementation while the current branch is `main`.
- The AI must not commit, push, merge, force-push, or delete branches without explicit developer approval.
- The AI must report required out-of-scope changes instead of making them silently.
- The developer must review `git diff` before accepting, committing, or pushing AI-generated work.

## Four rules to remember

1. Never work or push directly on `main`.
2. Pull the latest `main` before creating a task branch.
3. Use one branch for one task.
4. Review `git diff` before committing and merging.
