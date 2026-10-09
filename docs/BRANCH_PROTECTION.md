# Settings for the repository owner to apply

No `gh` CLI is available to the assistant, so apply these in GitHub (Settings):

1. **Default branch:** change to `main` (Settings → General → Default branch).
2. **Visibility:** Settings → General → Danger zone → make the repository **private** (currently public).
3. **Branch protection for `main`** (Settings → Branches → Add rule):
   - Require a pull request before merging.
   - Require status checks to pass: all `CI / ubuntu-latest / py3.11|3.13` and `CI / windows-latest / py3.11|3.13` jobs.
   - Require branches to be up to date; block force pushes and deletions.
4. Actions → General: allow only actions pinned by SHA (optional hardening).
