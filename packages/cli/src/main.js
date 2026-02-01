const { Command } = require("commander");

const { contract } = require("@mailbox/shared");
const { accounts, email, imap, smtp, sync } = require("@mailbox/core");
const { digest, monitor, inbox } = require("@mailbox/workflows");

function _printTextNotImplemented(label) {
  process.stdout.write(`${label} (text mode) is not implemented yet. Use --json.\n`);
}

async function main(argv) {
  const parsed = contract.parseGlobalFlags(argv);
  const asJson = parsed.asJson;
  const pretty = parsed.pretty;

  const program = new Command();
  program.name("mailbox");
  program.exitOverride();

  const accountCmd = program.command("account").description("Account operations");
  accountCmd
    .command("list")
    .description("List configured accounts")
    .action(() => {
      const result = accounts.listAccounts();
      const rc = contract.handleJsonOrText({
        result,
        asJson,
        pretty,
        printText: (r) => {
          const rows = r.accounts || [];
          if (!rows.length) {
            process.stdout.write("No accounts configured.\n");
            return;
          }
          process.stdout.write("ID\tEmail\tProvider\n");
          for (const a of rows) {
            process.stdout.write(`${a.id}\t${a.email || ""}\t${a.provider || ""}\n`);
          }
        },
      });
      process.exit(rc);
    });

  accountCmd
    .command("test-connection")
    .description("Test IMAP/SMTP connectivity")
    .option("--account-id <id>", "Specific account id/email")
    .action(async (opts) => {
      let result;

      try {
        const accId = String(opts.accountId || "").trim();
        let targets = [];

        if (accId) {
          const one = accounts.getAccountByIdOrEmail(accId);
          if (!one.success) {
            result = { success: false, error: one.error || `Account not found: ${accId}`, accounts: [], total_accounts: 0 };
          } else {
            targets = [one.account];
          }
        } else {
          const all = accounts.getAllAccountsResolved();
          if (!all.success) {
            result = all;
          } else {
            targets = all.accounts || [];
            if (!targets.length) {
              result = { success: false, error: "No accounts configured", accounts: [], total_accounts: 0 };
            }
          }
        }

        if (!result) {
          const out = [];
          for (const a of targets) {
            const item = {
              email: a.email,
              provider: a.provider,
              success: false,
              imap: { success: false },
              smtp: { success: false },
            };

            try {
              // eslint-disable-next-line no-await-in-loop
              const im = await imap.testConnection(a, "INBOX");
              item.imap = { success: Boolean(im && im.success), total_emails: im.total_emails || 0, unread_emails: im.unread_emails || 0 };
              if (im && im.error) item.imap.error = im.error;
            } catch (e) {
              item.imap = { success: false, error: e && e.message ? e.message : "IMAP failed" };
            }

            try {
              // eslint-disable-next-line no-await-in-loop
              const sm = await smtp.testConnection(a);
              item.smtp = { success: Boolean(sm && sm.success) };
              if (sm && sm.error) item.smtp.error = sm.error;
            } catch (e) {
              item.smtp = { success: false, error: e && e.message ? e.message : "SMTP failed" };
            }

            item.success = Boolean(item.imap && item.imap.success) && Boolean(item.smtp && item.smtp.success);
            out.push(item);
          }

          result = { success: out.length > 0 && out.every((x) => x.success), accounts: out, total_accounts: out.length };
        }
      } catch (e) {
        result = { success: false, error: e && e.message ? e.message : "test failed" };
      }

      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("account test-connection") });
      process.exit(rc);
    });

  // email
  const emailCmd = program.command("email").description("Email operations");
  emailCmd
    .command("list")
    .description("List emails")
    .option("--limit <n>", "Limit", "100")
    .option("--offset <n>", "Offset", "0")
    .option("--unread-only", "Only unread")
    .option("--account-id <id>", "Account id/email")
    .option("--folder <name>", "Folder", "all")
    .option("--live", "Force live IMAP (no cache)")
    .action(async (opts) => {
      const result = await email.listEmails({
        limit: Number(opts.limit),
        offset: Number(opts.offset),
        unread_only: Boolean(opts.unreadOnly),
        folder: opts.folder,
        account_id: opts.accountId || "",
        use_cache: !Boolean(opts.live),
      });
      // Add contract parity fields.
      result.limit = Number(opts.limit);
      result.offset = Number(opts.offset);
      result.unread_only = Boolean(opts.unreadOnly);
      result.folder = opts.folder;
      result.use_cache = !Boolean(opts.live);
      if (opts.accountId) result.account_id = opts.accountId;

      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email list") });
      process.exit(rc);
    });

  emailCmd
    .command("search")
    .description("Search emails")
    .requiredOption("--query <q>", "Query")
    .option("--account-id <id>")
    .option("--date-from <s>")
    .option("--date-to <s>")
    .option("--limit <n>", "Limit", "50")
    .option("--offset <n>", "Offset", "0")
    .option("--unread-only")
    .option("--folder <name>", "Folder", "all")
    .action(async (opts) => {
      const result = await email.searchEmails({
        query: opts.query,
        account_id: opts.accountId || "",
        date_from: opts.dateFrom || "",
        date_to: opts.dateTo || "",
        limit: Number(opts.limit),
        offset: Number(opts.offset),
        unread_only: Boolean(opts.unreadOnly),
        folder: opts.folder,
      });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email search") });
      process.exit(rc);
    });

  emailCmd
    .command("show")
    .description("Show email detail")
    .argument("<email_id>")
    .option("--account-id <id>")
    .option("--folder <name>", "Folder", "INBOX")
    .action(async (emailId, opts) => {
      const result = await email.showEmail({ email_id: emailId, folder: opts.folder, account_id: opts.accountId || "" });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email show") });
      process.exit(rc);
    });

  emailCmd
    .command("mark")
    .description("Mark emails read/unread")
    .argument("<email_ids...>")
    .option("--read", "Mark as read")
    .option("--unread", "Mark as unread")
    .option("--account-id <id>")
    .option("--folder <name>", "Folder", "INBOX")
    .option("--dry-run")
    .action(async (ids, opts) => {
      const read = Boolean(opts.read);
      const unread = Boolean(opts.unread);
      if ((read && unread) || (!read && !unread)) {
        const rc = contract.invalidUsage({ message: "Specify exactly one of --read/--unread", asJson, pretty });
        process.exit(rc);
      }

      const mark_as = unread ? "unread" : "read";
      const result = await email.markEmails({
        email_ids: ids,
        mark_as,
        folder: opts.folder,
        account_id: opts.accountId || "",
        dry_run: Boolean(opts.dryRun),
      });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email mark") });
      process.exit(rc);
    });

  emailCmd
    .command("delete")
    .description("Delete emails")
    .argument("<email_ids...>")
    .option("--account-id <id>")
    .option("--folder <name>", "Folder", "INBOX")
    .option("--permanent")
    .option("--trash-folder <name>", "Trash folder", "Trash")
    .option("--dry-run")
    .action(async (ids, opts) => {
      const result = await email.deleteEmails({
        email_ids: ids,
        folder: opts.folder,
        permanent: Boolean(opts.permanent),
        trash_folder: opts.trashFolder,
        account_id: opts.accountId || "",
        dry_run: Boolean(opts.dryRun),
      });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email delete") });
      process.exit(rc);
    });

  emailCmd
    .command("send")
    .description("Send an email")
    .requiredOption("--to <to...>")
    .requiredOption("--subject <s>")
    .option("--body <text>")
    .option("--body-file <path>")
    .option("--cc <cc...>")
    .option("--bcc <bcc...>")
    .option("--account-id <id>")
    .option("--is-html")
    .action(async (opts) => {
      const hasBody = typeof opts.body === "string" && opts.body.length;
      const hasBodyFile = Boolean(opts.bodyFile);
      if ((hasBody && hasBodyFile) || (!hasBody && !hasBodyFile)) {
        const rc = contract.invalidUsage({ message: "Specify exactly one of --body/--body-file", asJson, pretty });
        process.exit(rc);
      }

      let body = opts.body || "";
      if (opts.bodyFile) {
        try {
          body = require("fs").readFileSync(opts.bodyFile, "utf8");
        } catch (e) {
          const rc = contract.invalidUsage({ message: e && e.message ? e.message : "Failed to read body file", asJson, pretty });
          process.exit(rc);
        }
      }
      const result = await email.sendEmail({
        to: opts.to,
        subject: opts.subject,
        body,
        cc: opts.cc,
        bcc: opts.bcc,
        account_id: opts.accountId || "",
        is_html: Boolean(opts.isHtml),
      });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email send") });
      process.exit(rc);
    });

  emailCmd
    .command("reply")
    .description("Reply to an email")
    .argument("<email_id>")
    .option("--body <text>")
    .option("--body-file <path>")
    .option("--reply-all")
    .option("--folder <name>", "Folder", "INBOX")
    .option("--account-id <id>")
    .option("--is-html")
    .action(async (emailId, opts) => {
      const hasBody = typeof opts.body === "string" && opts.body.length;
      const hasBodyFile = Boolean(opts.bodyFile);
      if ((hasBody && hasBodyFile) || (!hasBody && !hasBodyFile)) {
        const rc = contract.invalidUsage({ message: "Specify exactly one of --body/--body-file", asJson, pretty });
        process.exit(rc);
      }

      let body = opts.body || "";
      if (opts.bodyFile) {
        try {
          body = require("fs").readFileSync(opts.bodyFile, "utf8");
        } catch (e) {
          const rc = contract.invalidUsage({ message: e && e.message ? e.message : "Failed to read body file", asJson, pretty });
          process.exit(rc);
        }
      }
      const result = await email.replyEmail({
        email_id: emailId,
        body,
        reply_all: Boolean(opts.replyAll),
        folder: opts.folder,
        account_id: opts.accountId || "",
        is_html: Boolean(opts.isHtml),
      });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email reply") });
      process.exit(rc);
    });

  emailCmd
    .command("forward")
    .description("Forward an email")
    .argument("<email_id>")
    .requiredOption("--to <to...>")
    .option("--body <text>")
    .option("--folder <name>", "Folder", "INBOX")
    .option("--no-attachments")
    .option("--account-id <id>")
    .action(async (emailId, opts) => {
      const result = await email.forwardEmail({
        email_id: emailId,
        to: opts.to,
        body: opts.body || "",
        folder: opts.folder,
        no_attachments: Boolean(opts.noAttachments),
        account_id: opts.accountId || "",
      });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email forward") });
      process.exit(rc);
    });

  emailCmd
    .command("folders")
    .description("List folders")
    .requiredOption("--account-id <id>")
    .action(async (opts) => {
      const result = await email.listFolders({ account_id: opts.accountId });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email folders") });
      process.exit(rc);
    });

  emailCmd
    .command("attachments")
    .description("Download attachments")
    .argument("<email_id>")
    .requiredOption("--account-id <id>")
    .option("--folder <name>", "Folder", "INBOX")
    .action(async (emailId, opts) => {
      const result = await email.downloadAttachments({ email_id: emailId, folder: opts.folder, account_id: opts.accountId });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email attachments") });
      process.exit(rc);
    });

  emailCmd
    .command("flag")
    .description("Flag/unflag an email")
    .argument("<email_id>")
    .requiredOption("--account-id <id>")
    .option("--set")
    .option("--unset")
    .option("--flag-type <t>", "Flag type", "flagged")
    .option("--folder <name>", "Folder", "INBOX")
    .action(async (emailId, opts) => {
      const set = Boolean(opts.set);
      const unset = Boolean(opts.unset);
      if ((set && unset) || (!set && !unset)) {
        const rc = contract.invalidUsage({ message: "Specify exactly one of --set/--unset", asJson, pretty });
        process.exit(rc);
      }

      const setFlag = set;
      const result = await email.flagEmail({
        email_id: emailId,
        set_flag: setFlag,
        flag_type: opts.flagType,
        folder: opts.folder,
        account_id: opts.accountId,
      });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email flag") });
      process.exit(rc);
    });

  emailCmd
    .command("move")
    .description("Move emails to folder")
    .argument("<email_ids...>")
    .requiredOption("--target-folder <name>")
    .option("--source-folder <name>", "Source folder", "INBOX")
    .requiredOption("--account-id <id>")
    .action(async (ids, opts) => {
      const result = await email.moveEmails({
        email_ids: ids,
        target_folder: opts.targetFolder,
        source_folder: opts.sourceFolder,
        account_id: opts.accountId,
      });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("email move") });
      process.exit(rc);
    });

  // sync
  const syncCmd = program.command("sync").description("Local sync/cache operations");
  syncCmd
    .command("status")
    .description("Show scheduler status")
    .action(() => {
      const result = sync.status();
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("sync status") });
      process.exit(rc);
    });
  syncCmd
    .command("force")
    .description("Force sync now")
    .option("--account-id <id>")
    .option("--full")
    .action(async (opts) => {
      const result = await sync.force({ account_id: opts.accountId || "", full: Boolean(opts.full) });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("sync force") });
      process.exit(rc);
    });
  syncCmd
    .command("init")
    .description("Initialize database and run initial sync")
    .action(async () => {
      const result = await sync.init();
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("sync init") });
      process.exit(rc);
    });
  syncCmd
    .command("health")
    .description("Show sync health summary")
    .action(() => {
      const result = sync.health();
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("sync health") });
      process.exit(rc);
    });

  syncCmd
    .command("watch")
    .description("Continuously print sync status")
    .option("--interval <seconds>", "Refresh interval", "5")
    .action(async (opts) => {
      const { printJson } = require("@mailbox/shared").json;
      const intervalSec = Math.max(0.5, Number(opts.interval || 5));
      try {
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const status = sync.status();
          status.success = true;
          printJson(status, Boolean(pretty) || !asJson);
          // eslint-disable-next-line no-await-in-loop
          await new Promise((r) => setTimeout(r, intervalSec * 1000));
        }
      } catch (e) {
        if (e && e.name === "AbortError") return process.exit(0);
        return process.exit(0);
      }
    });

  syncCmd
    .command("daemon")
    .description("Run periodic sync in the foreground")
    .option("--interval <seconds>", "Sync interval", "300")
    .option("--account-id <id>")
    .option("--full")
    .action(async (opts) => {
      const intervalSec = Math.max(5, Number(opts.interval || 300));
      try {
        // eslint-disable-next-line no-constant-condition
        while (true) {
          // eslint-disable-next-line no-await-in-loop
          await sync.force({ account_id: opts.accountId || "", full: Boolean(opts.full) });
          // eslint-disable-next-line no-await-in-loop
          await new Promise((r) => setTimeout(r, intervalSec * 1000));
        }
      } catch {
        return process.exit(0);
      }
    });

  // digest
  const digestCmd = program.command("digest").description("Daily digest workflows");
  digestCmd
    .command("run")
    .description("Run once")
    .option("--dry-run")
    .option("--debug-path <path>")
    .action(async (opts) => {
      const result = await digest.run({ dry_run: Boolean(opts.dryRun), debug_path: opts.debugPath || "" });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("digest run") });
      process.exit(rc);
    });
  digestCmd
    .command("config")
    .description("Print current configuration")
    .action(() => {
      const result = digest.getConfig();
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("digest config") });
      process.exit(rc);
    });

  digestCmd
    .command("daemon")
    .description("Run digest periodically in the foreground")
    .option("--interval <seconds>", "Interval", "3600")
    .option("--dry-run")
    .action(async (opts) => {
      const intervalSec = Math.max(5, Number(opts.interval || 3600));
      try {
        // eslint-disable-next-line no-constant-condition
        while (true) {
          // eslint-disable-next-line no-await-in-loop
          await digest.run({ dry_run: Boolean(opts.dryRun), debug_path: "" });
          // eslint-disable-next-line no-await-in-loop
          await new Promise((r) => setTimeout(r, intervalSec * 1000));
        }
      } catch {
        return process.exit(0);
      }
    });

  // monitor
  const monitorCmd = program.command("monitor").description("Email monitor workflows");
  monitorCmd
    .command("run")
    .description("Run one monitoring cycle")
    .action(async () => {
      const result = await monitor.run();
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("monitor run") });
      process.exit(rc);
    });
  monitorCmd
    .command("status")
    .description("Get monitoring status")
    .action(() => {
      const result = monitor.status();
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("monitor status") });
      process.exit(rc);
    });
  monitorCmd
    .command("config")
    .description("Print current configuration")
    .action(() => {
      const result = monitor.config();
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("monitor config") });
      process.exit(rc);
    });
  monitorCmd
    .command("test")
    .description("Test individual components")
    .argument("[component]", "fetch|notify|all", "all")
    .action((component) => {
      const result = monitor.test({ component });
      const rc = contract.handleJsonOrText({ result, asJson, pretty, printText: () => _printTextNotImplemented("monitor test") });
      process.exit(rc);
    });

  // inbox
  program
    .command("inbox")
    .description("Inbox organizer")
    .option("--limit <n>", "Analyze latest N emails", "15")
    .option("--folder <name>", "Folder", "INBOX")
    .option("--unread-only")
    .option("--account-id <id>")
    .option("--text")
    .action(async (opts) => {
      const result = await inbox.run({
        limit: Number(opts.limit),
        folder: opts.folder,
        unread_only: Boolean(opts.unreadOnly),
        account_id: opts.accountId || "",
      });
      const rc = contract.handleJsonOrText({
        result,
        asJson,
        pretty,
        printText: (r) => {
          if (opts.text && r && r.summary_text) process.stdout.write(String(r.summary_text) + "\n");
          else _printTextNotImplemented("inbox");
        },
      });
      process.exit(rc);
    });

  // Default interactive mode if no command.
  if (!parsed.argv.length) {
    return contract.invalidUsage({ message: "No command provided", asJson, pretty });
  }

  try {
    await program.parseAsync(["node", "mailbox", ...parsed.argv]);
    return 0;
  } catch (err) {
    // commander throws on invalid usage (exitOverride).
    const message = err && err.message ? err.message : "Invalid usage";
    return contract.invalidUsage({ message, asJson, pretty });
  }
}

module.exports = { main };
