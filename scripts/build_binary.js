#!/usr/bin/env node

const child_process = require("child_process");
const fs = require("fs");
const path = require("path");

function platformPackage() {
  const platform = process.platform;
  const arch = process.arch;

  if (platform === "darwin" && arch === "arm64") return "mailbox-cli-darwin-arm64";
  if (platform === "darwin" && arch === "x64") return "mailbox-cli-darwin-x64";
  if (platform === "linux" && arch === "x64") return "mailbox-cli-linux-x64-gnu";
  return null;
}

function pkgTarget() {
  const platform = process.platform;
  const arch = process.arch;

  // pkg currently supports up to Node 18 targets.
  if (platform === "darwin" && arch === "arm64") return "node18-macos-arm64";
  if (platform === "darwin" && arch === "x64") return "node18-macos-x64";
  if (platform === "linux" && arch === "x64") return "node18-linux-x64";
  return null;
}

function run(cmd, args) {
  child_process.execFileSync(cmd, args, { stdio: "inherit" });
}

function main() {
  const pkgName = platformPackage();
  const target = pkgTarget();
  if (!pkgName || !target) {
    console.error(`Unsupported platform for binary build: ${process.platform} ${process.arch}`);
    process.exit(1);
  }

  const entry = path.join(__dirname, "..", "packages", "cli", "bin", "mailbox.js");
  const outDir = path.join(__dirname, "..", "dist");
  fs.mkdirSync(outDir, { recursive: true });

  const outBin = path.join(outDir, "mailbox");
  console.log(`Building mailbox binary: target=${target}`);
  const root = path.join(__dirname, "..");
  run("pnpm", ["-C", root, "install"]);
  run("pnpm", ["-C", root, "test"]);
  run("pnpm", ["-C", root, "exec", "pkg", entry, "--targets", target, "--output", outBin]);

  const platformPkgDir = path.join(__dirname, "..", "mailbox-cli", "packages", pkgName);
  const binDir = path.join(platformPkgDir, "bin");
  fs.mkdirSync(binDir, { recursive: true });
  const dest = path.join(binDir, "mailbox");
  fs.copyFileSync(outBin, dest);
  fs.chmodSync(dest, 0o755);
  console.log(`Copied binary to: ${dest}`);
}

main();
