# Private GitHub access model

GitHub repository read access includes the repository source. A single repository
cannot provide binary-only user access while hiding source from those same readers.
Use two private repositories. A GitHub organization is required when user-tier
members must be read-only: private personal repositories only provide owner and
collaborator levels, and collaborators can both pull and push.

## Developer tier

Private repository: `parkhaven-source`.

- Teams: `parkhaven-developers` (Write) and `parkhaven-maintainers` (Maintain).
- Only owners/release administrators receive Admin.
- Protect the default branch: pull requests, one approval, resolved conversations,
  passing tests, no force pushes and no branch deletion.
- Disable or restrict private-repository forking where the organization plan allows.
- Store no API keys or deployment secrets in Git; use GitHub Environments/Secrets.

## User tier

Separate organization-owned private repository: `parkhaven-distribution`.

- Team: `parkhaven-users` with Read access only. This role is not available to
  collaborators on a private personal-account repository.
- Keep source code out of this repository. Commit only user documentation, support
  policy, release notes, checksums, notices and public signing certificates.
- Upload signed installers, SBOMs and release manifests as private GitHub Release
  assets. Users with Read access can download releases but cannot access the source
  repository unless separately added to the developer team.
- GitHub automatically offers source archives for every repository. In the
  distribution repository those archives contain only distribution metadata, not
  the application source.

## Important boundary

The current application is not yet a standalone user installer. It still depends on
the sibling analyser model/GHX and Three.js assets, a Python environment, Rhino 8,
the Rhino plug-in and WebView2. Do not invite user-tier recipients until a reviewed,
licensed and clean-machine-tested installer exists.

Review both team memberships periodically and remove access immediately when it is
no longer required. Repository privacy is access control, not DRM: authorized users
can retain any source or installer they can download.
