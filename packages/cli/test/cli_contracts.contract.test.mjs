import { describe, expect, it } from "vitest";
import { execa } from "execa";
import path from "node:path";
import fs from "node:fs";
import Ajv from "ajv";

import { defaultAuth, readSchema, testEnv, writeAuthJson } from "./_helpers.mjs";

const ajv = new Ajv({ allErrors: true, allowUnionTypes: true });

function expectValid(schemaName, payload) {
  const schema = readSchema(schemaName);
  const validate = ajv.compile(schema);
  const ok = validate(payload);
  if (!ok) {
    throw new Error(`Schema validation failed (${schemaName}): ${ajv.errorsText(validate.errors)}`);
  }
}

function tmpRoot(name) {
  return path.join(import.meta.dirname, ".tmp", name);
}

function mailboxBin() {
  return path.join(import.meta.dirname, "..", "bin", "mailbox.js");
}

describe("CLI JSON contract - MVP commands", () => {
  it("email list outputs emails array + totals", async () => {
    const root = tmpRoot("email_list");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const r = await execa(
      "node",
      [mailboxBin(), "email", "list", "--folder", "INBOX", "--account-id", "mock_acc", "--json"],
      {
        reject: false,
        env,
      }
    );

    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success");
    expect(payload).toHaveProperty("emails");
    expect(Array.isArray(payload.emails)).toBe(true);
    expect(payload).toHaveProperty("total_in_folder");
    expect(payload).toHaveProperty("unread_count");
    expect(payload).toHaveProperty("limit");
    expect(payload).toHaveProperty("offset");
    expect(payload).toHaveProperty("from_cache");
    expectValid("email_list.schema.json", payload);
  });

  it("email show outputs body + attachments metadata", async () => {
    const root = tmpRoot("email_show");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const r = await execa(
      "node",
      [mailboxBin(), "email", "show", "102", "--folder", "INBOX", "--account-id", "mock_acc", "--json"],
      {
        reject: false,
        env,
      }
    );

    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success", true);
    expect(payload).toHaveProperty("id");
    expect(payload).toHaveProperty("requested_id");
    expect(payload).toHaveProperty("subject");
    expect(payload).toHaveProperty("body");
    expect(payload).toHaveProperty("attachments");
    expect(Array.isArray(payload.attachments)).toBe(true);
    expect(payload).toHaveProperty("attachment_count");
    expectValid("email_show.schema.json", payload);
  });

  it("email attachments downloads and reports saved_path", async () => {
    const root = tmpRoot("email_attachments");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const r = await execa(
      "node",
      [mailboxBin(), "email", "attachments", "102", "--folder", "INBOX", "--account-id", "mock_acc", "--json"],
      {
        reject: false,
        env,
      }
    );

    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success", true);
    expect(payload).toHaveProperty("attachments");
    expect(Array.isArray(payload.attachments)).toBe(true);
    expect(payload).toHaveProperty("attachment_count");
    if (payload.attachment_count > 0) {
      expect(payload.attachments[0]).toHaveProperty("saved_path");
      expect(typeof payload.attachments[0].saved_path).toBe("string");
      expect(payload.attachments[0].saved_path.length).toBeGreaterThan(0);
    }
  });

  it("email mark dry-run returns would_mark + mark_as", async () => {
    const root = tmpRoot("email_mark");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const r = await execa(
      "node",
      [
        mailboxBin(),
        "email",
        "mark",
        "101",
        "102",
        "--read",
        "--folder",
        "INBOX",
        "--account-id",
        "mock_acc",
        "--dry-run",
        "--json",
      ],
      {
        reject: false,
        env,
      }
    );

    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success", true);
    expect(payload).toHaveProperty("dry_run", true);
    expect(payload).toHaveProperty("would_mark", 2);
    expect(payload).toHaveProperty("mark_as", "read");
    expect(payload).toHaveProperty("email_ids");
  });

  it("email delete dry-run returns would_delete", async () => {
    const root = tmpRoot("email_delete");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const r = await execa(
      "node",
      [mailboxBin(), "email", "delete", "101", "--folder", "INBOX", "--account-id", "mock_acc", "--dry-run", "--json"],
      {
        reject: false,
        env,
      }
    );

    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success", true);
    expect(payload).toHaveProperty("dry_run", true);
    expect(payload).toHaveProperty("would_delete", 1);
  });

  it("sync status returns scheduler fields", async () => {
    const root = tmpRoot("sync_status");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const r = await execa("node", [mailboxBin(), "sync", "status", "--json"], { reject: false, env });
    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success");
    expect(payload).toHaveProperty("scheduler_running");
    expect(payload).toHaveProperty("accounts");
    expect(payload).toHaveProperty("database_size");
    expectValid("sync_status.schema.json", payload);
  });

  it("sync force populates cache db and email list can read from cache", async () => {
    const root = tmpRoot("sync_force_cache");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const force = await execa("node", [mailboxBin(), "sync", "force", "--account-id", "mock_acc", "--json"], { reject: false, env });
    expect(force.exitCode).toBe(0);
    const forcePayload = JSON.parse(force.stdout);
    expect(forcePayload).toHaveProperty("success");

    const list = await execa(
      "node",
      [mailboxBin(), "email", "list", "--folder", "INBOX", "--account-id", "mock_acc", "--json"],
      { reject: false, env }
    );
    expect(list.exitCode).toBe(0);
    const listPayload = JSON.parse(list.stdout);
    expect(listPayload).toHaveProperty("success");
    expect(listPayload).toHaveProperty("from_cache");
  });

  it("digest run returns expected top-level fields", async () => {
    const root = tmpRoot("digest_run");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const r = await execa("node", [mailboxBin(), "digest", "run", "--dry-run", "--json"], { reject: false, env });
    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success", true);
    expect(payload).toHaveProperty("date");
    expect(payload).toHaveProperty("total_emails");
    expect(payload).toHaveProperty("summary");
    expect(payload).toHaveProperty("dry_run", true);
    expectValid("digest_run.schema.json", payload);
  });

  it("monitor status returns config paths", async () => {
    const root = tmpRoot("monitor_status");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const r = await execa("node", [mailboxBin(), "monitor", "status", "--json"], { reject: false, env });
    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success", true);
    expect(payload).toHaveProperty("status");
    expect(payload.status).toHaveProperty("config_path");
    expectValid("monitor_status.schema.json", payload);
  });

  it("inbox returns organizer shape", async () => {
    const root = tmpRoot("inbox");
    fs.rmSync(root, { recursive: true, force: true });

    const env = testEnv(root);
    writeAuthJson(env.MAILBOX_CONFIG_DIR, defaultAuth());

    const r = await execa("node", [mailboxBin(), "inbox", "--limit", "2", "--account-id", "mock_acc", "--json"], { reject: false, env });
    expect(r.exitCode).toBe(0);
    const payload = JSON.parse(r.stdout);
    expect(payload).toHaveProperty("success", true);
    expect(payload).toHaveProperty("processed");
    expect(payload).toHaveProperty("actions");
    expect(payload).toHaveProperty("stats");
    expectValid("inbox.schema.json", payload);
  });
});
