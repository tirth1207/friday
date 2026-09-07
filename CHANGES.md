# FRIDAY — Changes

## Git Mutation Workflow

**Branch:** `feat/git-mutation-workflow`

### What changed

- Added explicit Git mutation capabilities for the Developer Agent:
  - `git.add` — stage selected files.
  - `git.commit` — create a local commit with an explicit message.
  - `git.push` — push an approved branch/ref to its configured remote.
- Kept mutation operations permission-gated through FRIDAY's existing executor.
- Added the mutation tools to the Developer Agent's available tool set for the approved implementation/finalization phase.
- Preserved the existing inspect → implement → verify workflow and its requirement for concrete verification evidence.
- Added documentation for the intended approval boundary: code changes and verification happen first; staging, committing, and pushing remain explicit mutation operations.

### Safety notes

- No secrets are added to the repository.
- GitHub OAuth tokens remain outside Git command arguments.
- No direct mutation of `main` is intended by this branch.
- This branch is prepared as an isolated review checkpoint.

### Verification

The change should be validated in the local FRIDAY workspace with the project's normal test/build checks before merging.
