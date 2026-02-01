# mailbox-cli (npm)

This repository publishes the `mailbox-cli` npm package.

Goal: `npm i -g mailbox-cli` gives users a `mailbox` command **without** needing
Python or the source repo.

Distribution model:

- `mailbox-cli` (main package): provides the `mailbox` command (JS launcher)
- Platform packages (optional deps) ship the actual `mailbox` binary:
  - `mailbox-cli-darwin-arm64`
  - `mailbox-cli-darwin-x64`
  - `mailbox-cli-linux-x64-gnu`

The main package selects the correct platform package at runtime and executes
its bundled binary.

## Build inputs

The `mailbox` binary is built upstream from the Python codebase and attached to
a GitHub Release. This repo's release pipeline downloads those artifacts and
publishes them to npm.
