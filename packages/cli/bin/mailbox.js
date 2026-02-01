#!/usr/bin/env node

const { spawnSync } = require("child_process");

const { main } = require("../src/main");

function _shouldInteractive(argv) {
  if (argv.length) return false;
  if (String(process.env.MAILBOX_FORCE_INTERACTIVE || "") === "1") return true;
  return Boolean(process.stdin.isTTY && process.stdout.isTTY);
}

function _splitArgs(line) {
  const out = [];
  let cur = "";
  let quote = "";
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quote) {
      if (ch === quote) {
        quote = "";
        continue;
      }
      if (ch === "\\" && i + 1 < line.length) {
        cur += line[i + 1];
        i += 1;
        continue;
      }
      cur += ch;
      continue;
    }
    if (ch === "\"" || ch === "'") {
      quote = ch;
      continue;
    }
    if (ch === " " || ch === "\t") {
      if (cur) {
        out.push(cur);
        cur = "";
      }
      continue;
    }
    cur += ch;
  }
  if (cur) out.push(cur);
  return out;
}

async function _interactiveLoop() {
  const readline = require("readline");
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

  process.stdout.write("Mailbox interactive mode. Type `help` or `exit`.\n");
  rl.setPrompt("mailbox> ");
  rl.prompt();

  return await new Promise((resolve) => {
    rl.on("line", (line) => {
      const raw = String(line || "").trim();
      if (!raw) {
        rl.prompt();
        return;
      }
      if (raw === "exit" || raw === "quit") {
        rl.close();
        return;
      }
      if (raw === "help") {
        process.stdout.write("Examples:\n");
        process.stdout.write("  account list\n");
        process.stdout.write("  email list --folder INBOX --account-id <id>\n");
        process.stdout.write("  sync status\n");
        rl.prompt();
        return;
      }

      const args = _splitArgs(raw);
      // In a pkg binary, `__filename` points to a snapshot path and must NOT be
      // passed as argv[1]. Re-invoke the binary directly.
      const childArgs = process.pkg ? args : [__filename, ...args];
      const r = spawnSync(process.execPath, childArgs, { stdio: "inherit", env: process.env });
      if (typeof r.status === "number" && r.status !== 0) {
        process.stdout.write(`(exit ${r.status})\n`);
      }
      rl.prompt();
    });

    rl.on("close", () => resolve(0));
  });
}

Promise.resolve()
  .then(async () => {
    const argv = process.argv.slice(2);
    if (_shouldInteractive(argv)) {
      return await _interactiveLoop();
    }
    return await main(argv);
  })
  .then((code) => {
    process.exit(typeof code === "number" ? code : 0);
  })
  .catch((err) => {
    const msg = err && err.message ? err.message : String(err || "Error");
    process.stderr.write(msg + "\n");
    process.exit(1);
  });
