import fs from "node:fs";
import path from "node:path";

export function readSchema(name) {
  const repoRoot = path.resolve(import.meta.dirname, "..", "..", "..");
  const p = path.join(repoRoot, "docs", "cli_json_schemas", name);
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

export function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

export function writeAuthJson(configDir, auth) {
  ensureDir(configDir);
  const p = path.join(configDir, "auth.json");
  fs.writeFileSync(p, JSON.stringify(auth, null, 2) + "\n", "utf8");
  return p;
}

export function testEnv(tmpRoot) {
  return {
    ...process.env,
    MAILBOX_TEST_MODE: "1",
    MAILBOX_CONFIG_DIR: path.join(tmpRoot, "config"),
    MAILBOX_DATA_DIR: path.join(tmpRoot, "data"),
  };
}

export function defaultAuth() {
  return {
    version: 1,
    accounts: {
      mock_acc: {
        email: "mock@example.com",
        password: "mock",
        provider: "mock",
        description: "Mock account",
      },
    },
    default_account: "mock_acc",
  };
}
