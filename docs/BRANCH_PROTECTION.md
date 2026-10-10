# Settings for the repository owner to apply

These are GitHub settings that only the repository owner can change; the assistant that builds the tool has no `gh` CLI and works through pull requests only. Status as checked on 2026-10-10 (from the GitHub API and the workflow files); tick them off when done.

1. **Default branch:** `main`. *Done* (the API reports `main`).
2. **Visibility:** the specification says the repository must be **private** (project data may be export-controlled) and to stop and ask if it is public. The API reports it as **public**. *Open*: Settings → General → Danger zone → change visibility to private, or decide that a public repository is acceptable because the examples contain invented data only (and then decide the licence question, see [DOCS_AUDIT.md](DOCS_AUDIT.md)).
3. **Branch protection for `main`** (Settings → Branches → Add rule). *Open* (not verifiable from here):
   - Require a pull request before merging.
   - Require status checks to pass: all `CI / ubuntu-latest / py3.11`, `py3.13` and `CI / windows-latest / py3.11`, `py3.13` jobs.
   - Require branches to be up to date; block force pushes and deletions.
4. **Actions → General:** allow only actions pinned by SHA (optional hardening). The workflows already pin every action to a commit SHA.

Next: [Docs index](README.md) · [Developer docs](developer/README.md).
