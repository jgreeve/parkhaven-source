# Private GitHub setup guide

This guide starts with two private repositories under a personal GitHub account:

- `parkhaven-source`: source code, available only to approved developers.
- `parkhaven-distribution`: user documentation and private release downloads,
  without application source code.

GitHub cannot hide source from someone who has Read access to the same repository.
The two-repository boundary is therefore required for separate user and developer
access. There is an important personal-account limitation: collaborators on a
private personal repository always receive both read and write access. GitHub does
not offer a read-only collaborator role there. To enforce a true read-only user
tier, put `parkhaven-distribution` in a GitHub organization or use another private
artifact-download service.

## 1. Install GitHub CLI

Open PowerShell as Administrator and run:

```powershell
winget install --id GitHub.cli --exact
```

Close and reopen PowerShell, then verify:

```powershell
gh --version
```

If `gh` is still not found, restart Windows or add the GitHub CLI installation
folder to `PATH`.

## 2. Authenticate securely

Run:

```powershell
gh auth login --web --git-protocol https
gh auth status
```

Choose `GitHub.com` and complete the browser confirmation. Never paste a personal
access token into project files, chat, documentation or shell scripts.

Get your username and account ID:

```powershell
$login = gh api user --jq .login
$accountId = gh api user --jq .id
"$login / $accountId"
```

## 3. Configure private commit identity

Git commit metadata is visible to everyone with source-repository access. Use your
GitHub private noreply address rather than a personal email:

```powershell
$login = gh api user --jq .login
$accountId = gh api user --jq .id
git config user.name $login
git config user.email "$accountId+$login@users.noreply.github.com"
git config --get user.name
git config --get user.email
```

These commands configure only this repository when run from its folder. Do not add
`--global` unless you want the same identity for all repositories on this computer.

## 4. Open the source project

If the PowerShell prompt already ends with `ParkHaven_App_v0.1>`, you are in the
correct folder and can skip `Set-Location`. Otherwise run this command after
replacing the example path with the real project path:

```powershell
Set-Location -LiteralPath "C:\path\to\ParkHaven_App_v0.1"
```

If PowerShell shows a `>>` prompt, it is waiting for a closing quote or bracket.
Press `Ctrl+C` to cancel that incomplete command and return to the normal `PS ...>`
prompt before continuing.

The repository has already been initialized on branch `main`. Confirm the exact
candidate before the first commit:

```powershell
git status --short
git diff --cached --check
git diff --cached --stat
```

Expected boundary:

- approximately 79 source/documentation files are staged;
- `.venv`, `bin`, `obj`, caches, raw verification JSON and project workspaces are
  not staged;
- `config/ai-trust.local.json`, the deployment certificate and private endpoint are
  ignored;
- no `.3dm`, `.gh`, `.ghx`, logs, PDB files or copied Rhino assemblies are staged.

Inspect ignored sensitive files:

```powershell
git status --short --ignored
git check-ignore -v `
  "config/ai-trust.local.json" `
  "docs/view_evidence_verification.json" `
  ".venv/Scripts/python.exe"
```

## 5. Run final checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check .\app\static\app.js
node --check .\app\static\viewer.js
```

The current verified baseline is 89 passing Python tests with one known Starlette
TestClient deprecation warning.

## 6. Create the initial source commit

Review the staged files one final time, then commit:

```powershell
git commit -m "Initial private ParkHaven source import"
git status --short
git log --oneline -1
```

Do not use `git add -f` to bypass ignore rules.

## 7. Create and push the private source repository

Create it as **private** and push `main`:

```powershell
gh repo create parkhaven-source `
  --private `
  --source . `
  --remote origin `
  --push `
  --description "Confidential ParkHaven desktop application source"
```

Verify privacy immediately:

```powershell
gh repo view --json nameWithOwner,visibility,url
git remote -v
```

The output must report `PRIVATE`. If it does not, change visibility immediately in
GitHub repository **Settings > General > Danger Zone** and review access/audit logs.

## 8. Protect the source repository

In GitHub, open `parkhaven-source`:

1. Open **Settings > Collaborators** and invite developers only.
2. Give normal developers **Write** access, not Admin.
3. Keep Admin access limited to the owner or release administrator.
4. Open **Settings > Rules > Rulesets** or **Branches**.
5. Protect `main` with pull requests, at least one approval, resolved conversations,
   passing checks, blocked force pushes and blocked deletion.
6. Disable private-repository forking if the available account plan exposes that
   option and you do not need forks.
7. Keep Issues and Discussions private to repository collaborators or disable them.

On a personal repository, roles and ruleset features depend on the GitHub plan. If
you need reusable teams such as `parkhaven-developers` and `parkhaven-users`, move
both repositories into a private GitHub organization later.

## 9. Create the user distribution repository

Do not run `gh repo create --source .` for this repository. That would push the
application source into the user tier.

Create an empty private repository:

```powershell
gh repo create parkhaven-distribution `
  --private `
  --description "Private ParkHaven user releases and documentation"
```

Create a separate local folder outside the source repository:

```powershell
$distribution = Join-Path $HOME "Documents\parkhaven-distribution"
New-Item -ItemType Directory -Path $distribution
Set-Location -LiteralPath $distribution
git init -b main
```

Add only distribution metadata such as:

```text
README.md
USER_GUIDE.md
RELEASE_NOTES.md
SUPPORT.md
EULA.txt
THIRD_PARTY_NOTICES.txt
checksums/
manifests/
```

Do not add Python, JavaScript, C#, GHX, 3DM, developer tests, credentials, PDB files,
raw evidence or project workspaces. Commit and connect the empty repository:

```powershell
git add .
git commit -m "Initialize private distribution repository"
$login = gh api user --jq .login
git remote add origin "https://github.com/$login/parkhaven-distribution.git"
git push -u origin main
```

## 10. Add user-tier access

Do not invite end users to a personal-account distribution repository under the
assumption that they are read-only. GitHub documents that collaborators on private
personal repositories can pull and push.

### Recommended: organization-owned distribution

Create a GitHub organization, transfer `parkhaven-distribution` to it, then:

1. Open **Settings > Collaborators**.
2. Create a `parkhaven-users` team with **Read** repository access.
3. Add approved users to that team.
4. Keep developers in a separate `parkhaven-developers` team.
5. Do not grant the user team access to `parkhaven-source`.
6. Remove access immediately when no longer required.

You may keep `parkhaven-source` under your personal account if developers are
allowed to write, although moving both repositories into the organization gives
cleaner team management.

### Personal-account alternatives

- Accept that every invited distribution collaborator has write access, and protect
  `main` with the strongest available rules. This still allows broader release and
  repository actions and is not a true user tier.
- Do not invite users to GitHub. Deliver signed installers through a private portal,
  managed cloud storage, or another service that supports download-only access.
- Create the organization before distributing anything. This is the preferred path.

Repository privacy prevents uninvited GitHub accounts from browsing or cloning the
repository. It does not provide DRM: anyone with legitimate download access can
retain or redistribute files they have downloaded. Use contracts/EULA and signed
artifacts where appropriate.

## 11. Publish releases safely

The application is not yet ready for a user release. It still depends on the sibling
analyser model/GHX and Three.js assets, a Python environment, Rhino 8, the Rhino
plug-in and WebView2. Complete the installer/licensing work before inviting users.

When a reviewed installer exists:

1. Build it from a protected source tag on a clean machine or CI worker.
2. Exclude `.venv`, source files, PDBs, copied Rhino assemblies, project models,
   credentials, raw logs and generated evidence.
3. Code-sign the installer.
4. Generate SHA-256 checksums, an SBOM and release manifest.
5. Include the EULA and complete third-party notices.
6. Upload installers as private GitHub Release assets, not ordinary Git commits.
7. Never replace an artifact under an existing version tag.

Example release command after the artifacts exist:

```powershell
gh release create v0.1.0 `
  ".\ParkHaven-Setup-v0.1.0.exe" `
  ".\SHA256SUMS.txt" `
  ".\sbom.cdx.json" `
  --repo "$login/parkhaven-distribution" `
  --title "ParkHaven v0.1.0" `
  --notes-file ".\RELEASE_NOTES.md"
```

## 12. Routine checks before every push

From the source repository:

```powershell
git status
git diff
git diff --cached
git diff --cached --check
git log --oneline -10
```

Confirm that no secrets or personal paths are staged. Never commit from a broad ZIP
or GitHub web upload; Git ignore rules protect `git add`, not arbitrary archive or
browser uploads.

## Current local status

At the time this guide was created:

- branch `main` exists locally;
- the sanitized initial source tree is staged but not committed;
- no remote is configured;
- no Git author identity is configured;
- GitHub CLI still needs successful installation/authentication;
- all 89 Python tests pass;
- raw personal/device verification records remain local and ignored.
