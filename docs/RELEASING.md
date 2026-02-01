# Releasing (mailbox + mailbox-cli)

This project ships:

1) A standalone `mailbox` binary (built from this repo)
2) An npm package `mailbox-cli` that installs `mailbox` (binary distribution)

## 1) Build + publish `mailbox` binaries

Create a tag:

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

## 2) Publish `mailbox-cli` to npm

The Node project lives under `mailbox-cli/`.

Publishing model:

- `mailbox-cli` main package depends on platform packages:
  - `mailbox-cli-darwin-arm64`
  - `mailbox-cli-darwin-x64`
  - `mailbox-cli-linux-x64-gnu`

Each platform package bundles a `bin/mailbox` executable.

Release pipeline (expected):

1. Download GitHub Release assets for the same version.
2. Extract `dist/mailbox` into the right platform package `bin/mailbox`.
3. Set executable bit on unix platforms.
4. Publish platform packages first, then publish `mailbox-cli`.

Note: the `mailbox-cli/` directory is intended to become its own repo.

### Required files in each platform package

Each platform package must contain:

- `bin/mailbox` (executable)
- `index.js` exporting `binaryPath`

The launcher package `mailbox-cli` resolves the correct platform package and
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
