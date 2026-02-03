# Releasing (mailbox + mailbox-cli)

This project ships:

1) A standalone `mailbox` binary (built from this repo)
2) An npm package `@leeguoo/mailbox-cli` that installs `mailbox` (binary distribution)

## Automated release (recommended)

Releases are created automatically from `main` using semantic-release.

Requirements:
- Conventional Commit messages (`feat:`, `fix:`, etc.)
- Do **not** manually bump package versions in `mailbox-cli/packages/*`
  (keep them at `0.0.0`). The CI publish job sets real versions at release
  time via `scripts/set_release_version.js`.
- Set repository secret `RELEASE_TOKEN` (a PAT with `repo` + `workflow` scopes)
  so tag pushes can trigger `publish-npm` and `release-binaries`.

Flow:
1. Merge to `main` with a `feat:` or `fix:` commit.
2. The `semantic-release` workflow computes the next version and pushes a tag
   like `v2.0.6`.
3. Tag push triggers `release-binaries` and `publish-npm`.

If no release-worthy commits are found, semantic-release exits without tagging.

## Manual release (fallback)

## 1) Build + publish `mailbox` binaries

Create a tag (only if you are not using semantic-release):

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

GitHub Actions workflow `release-binaries` will build and attach artifacts to a
GitHub Release:

- `mailbox-darwin-arm64.tar.gz`
- `mailbox-darwin-x64.tar.gz`
- `mailbox-linux-x64-gnu.tar.gz`

Each has a matching `.sha256` file.

## 2) Publish `@leeguoo/mailbox-cli` to npm

The Node project lives under `mailbox-cli/`.

Publishing model:

- `@leeguoo/mailbox-cli` main package depends on platform packages:
  - `@leeguoo/mailbox-cli-darwin-arm64`
  - `@leeguoo/mailbox-cli-darwin-x64`
  - `@leeguoo/mailbox-cli-linux-x64-gnu`

Each platform package bundles a `bin/mailbox` executable.

Release pipeline (automated):

This repository uses GitHub Actions to publish npm packages from a git tag.

Required secret:

- `NPM_TOKEN` (an npm access token with publish rights)

Flow:

1. Push a tag `vX.Y.Z`.
2. CI builds the `mailbox` binary on each target OS.
3. CI injects the binary into each platform package `bin/mailbox`.
4. CI sets `package.json` versions to `X.Y.Z` (platform packages + launcher).
5. CI publishes platform packages first, then publishes `@leeguoo/mailbox-cli`.

Workflow:

- `.github/workflows/publish-npm.yml`

Note: the `mailbox-cli/` directory is intended to become its own repo.

### Required files in each platform package

Each platform package must contain:

- `bin/mailbox` (executable)
- `index.js` exporting `binaryPath`

The launcher package `@leeguoo/mailbox-cli` resolves the correct platform package and
executes `binaryPath`.

### Artifact naming convention

`release-binaries` uploads:

- `mailbox-darwin-arm64.tar.gz`
- `mailbox-darwin-x64.tar.gz`
- `mailbox-linux-x64-gnu.tar.gz`

These tarballs contain a single file: `mailbox`.

The npm release pipeline should:

1. Download the tarball matching the platform package.
2. Extract `mailbox` into `packages/<platform>/bin/mailbox`.
3. Ensure unix executable bit is set (chmod +x).
