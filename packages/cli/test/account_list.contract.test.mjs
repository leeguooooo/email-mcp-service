import { describe, expect, it } from "vitest";
import { execa } from "execa";
import path from "node:path";
import Ajv from "ajv";

import { readSchema } from "./_helpers.mjs";

const ajv = new Ajv({ allErrors: true, allowUnionTypes: true });

function expectValid(schemaName, payload) {
  const schema = readSchema(schemaName);
  const validate = ajv.compile(schema);
  const ok = validate(payload);
  if (!ok) {
    throw new Error(`Schema validation failed (${schemaName}): ${ajv.errorsText(validate.errors)}`);
  }
}

describe("CLI JSON contract - account list", () => {
  it("outputs a single JSON object with success/accounts/count", async () => {
    const bin = path.join(import.meta.dirname, "..", "bin", "mailbox.js");
    const r = await execa("node", [bin, "account", "list", "--json"], {
      reject: false,
      env: {
        ...process.env,
        // Ensure deterministic empty config location for tests.
        MAILBOX_CONFIG_DIR: path.join(import.meta.dirname, ".tmp_config"),
        MAILBOX_DATA_DIR: path.join(import.meta.dirname, ".tmp_data"),
      },
    });

    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success");
    expect(typeof payload.success).toBe("boolean");
    expect(payload).toHaveProperty("accounts");
    expect(Array.isArray(payload.accounts)).toBe(true);
    expect(payload).toHaveProperty("count");
    expect(typeof payload.count).toBe("number");
    expectValid("account_list.schema.json", payload);
  });
});
