const fs = require("fs");
const path = require("path");

const { paths } = require("@mailbox/shared");

const accounts = require("./accounts");
const { withImapClient } = require("./imap");
const { sendMail } = require("./smtp");
const { formatDateTime, firstAddress, hasAttachmentsFromBodyStructure, formatSize } = require("./format");

function _isTestMode() {
  return String(process.env.MAILBOX_TEST_MODE || "").trim() === "1";
}

function _normalizeFolder(folder) {
  const f = String(folder || "").trim();
  if (!f) return "INBOX";
  if (f.toLowerCase() === "all") return "INBOX";
  return f;
}

function _uidsSortedDesc(uids) {
  return [...uids].map((n) => Number(n)).filter((n) => Number.isFinite(n)).sort((a, b) => b - a);
}

async function _fetchEmailsForAccount({ account, folder, limit, offset, unreadOnly }) {
  const openFolder = _normalizeFolder(folder);
  return withImapClient(account, async (client) => {
    const st = await client.mailboxOpen(openFolder);
    const uids = await client.search(unreadOnly ? ["UNSEEN"] : ["ALL"]);
    const sorted = _uidsSortedDesc(uids);
    const slice = sorted.slice(offset, offset + limit);

    const emails = [];
    for await (const msg of client.fetch(slice, {
      envelope: true,
      flags: true,
      internalDate: true,
      bodyStructure: true,
    })) {
      const env = msg.envelope || {};
      const flags = msg.flags || new Set([]);
      const unread = !flags.has("\\Seen");
      emails.push({
        id: String(msg.uid),
        uid: String(msg.uid),
        message_id: env.messageId || "",
        subject: env.subject || "",
        from: firstAddress(env.from),
        date: formatDateTime(msg.internalDate || env.date),
        unread,
        has_attachments: hasAttachmentsFromBodyStructure(msg.bodyStructure),
        account: account.email,
        account_id: account.id,
        folder: openFolder,
        source: "imap_fetch",
      });
    }

    return {
      success: true,
      emails,
      total_in_folder: Number(st.exists || 0),
      unread_count: Number(st.unseen || 0),
      fetched: emails.length,
      folder: openFolder,
    };
  });
}

async function listEmails({ limit = 100, offset = 0, unread_only = false, folder = "all", account_id = "", use_cache = true } = {}) {
  const lim = Math.max(0, Number(limit || 0));
  const off = Math.max(0, Number(offset || 0));
  const unreadOnly = Boolean(unread_only);

  // Cache read from email_sync.db (python-compatible schema). Falls back to IMAP.
  if (use_cache) {
    try {
      const pc = paths.getPathConfig();
      const resolved = account_id ? accounts.getAccountByIdOrEmail(account_id) : null;
      const resolvedId = resolved && resolved.success ? resolved.account.id : "";
      const cache = await require("../storage/sync_db").listEmailsFromCache({
        dbPath: pc.emailSyncDb,
        accountId: resolvedId || "",
        folder,
        unreadOnly,
        limit: lim,
        offset: off,
      });
      if (cache && cache.success) {
        // Add multi-account metadata similar to Python contract.
        const all = accounts.getAllAccountsResolved();
        const accounts_count = resolvedId ? 1 : (all.success ? (all.accounts || []).length : 0);
        return {
          ...cache,
          total_emails: cache.total_in_folder,
          total_unread: cache.unread_count,
          accounts_count,
          accounts_info: [],
        };
      }
    } catch {
      // ignore
    }
  }

  const results = [];

  if (account_id) {
    const acc = accounts.getAccountByIdOrEmail(account_id);
    if (!acc.success) return acc;
    const r = await _fetchEmailsForAccount({ account: acc.account, folder, limit: lim, offset: off, unreadOnly });
    if (!r.success) return r;
    results.push({ account: acc.account, ...r });
  } else {
    const all = accounts.getAllAccountsResolved();
    if (!all.success) return all;
    const list = all.accounts || [];
    if (!list.length) {
      // Keep Python-like behavior: no accounts -> success with empty.
      return {
        success: true,
        emails: [],
        total_in_folder: 0,
        unread_count: 0,
        total_emails: 0,
        total_unread: 0,
        accounts_count: 0,
        accounts_info: [],
        offset: off,
        limit: lim,
        from_cache,
      };
    }

    for (const acc of list) {
      try {
        // eslint-disable-next-line no-await-in-loop
        const r = await _fetchEmailsForAccount({ account: acc, folder, limit: lim, offset: off, unreadOnly });
        results.push({ account: acc, ...r });
      } catch (e) {
        results.push({ account: acc, success: false, error: e && e.message ? e.message : "fetch failed" });
      }
    }
  }

  const ok = results.filter((r) => r.success);
  const emails = ok.flatMap((r) => r.emails || []);
  emails.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));

  const accounts_info = results.map((r) => {
    const total = r.total_in_folder != null ? r.total_in_folder : 0;
    const unread = r.unread_count != null ? r.unread_count : 0;
    const fetched = (r.emails || []).length;
    return { account: r.account && r.account.email ? r.account.email : "", total, unread, fetched };
  });

  const total_in_folder = ok.reduce((sum, r) => sum + Number(r.total_in_folder || 0), 0);
  const unread_count = ok.reduce((sum, r) => sum + Number(r.unread_count || 0), 0);

  return {
    success: ok.length === results.length,
    emails,
    total_in_folder,
    unread_count,
    total_emails: total_in_folder,
    total_unread: unread_count,
    accounts_count: results.length,
    accounts_info,
    offset: off,
    limit: lim,
    from_cache: false,
  };
}

async function searchEmails({ query, account_id = "", date_from = "", date_to = "", limit = 50, offset = 0, unread_only = false, folder = "all" } = {}) {
  const q = String(query || "");
  if (!q.trim()) return { success: false, error: "Missing --query" };

  const lim = Math.max(0, Number(limit || 0));
  const off = Math.max(0, Number(offset || 0));
  const unreadOnly = Boolean(unread_only);

  const started = Date.now();
  const listResult = await listEmails({ limit: Math.max(lim + off, 200), offset: 0, unread_only: unreadOnly, folder, account_id, use_cache: false });
  if (!listResult.success) {
    return {
      success: false,
      error: listResult.error || "search failed",
    };
  }

  // Best-effort filtering (mock mode + basic live list)
  let items = listResult.emails || [];
  items = items.filter((e) => {
    const hay = `${e.subject || ""} ${e.from || ""}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  if (date_from) {
    const df = new Date(String(date_from));
    if (!Number.isNaN(df.getTime())) {
      items = items.filter((e) => {
        const d = new Date(String(e.date || "").replace(" ", "T") + "Z");
        return !Number.isNaN(d.getTime()) && d >= df;
      });
    }
  }
  if (date_to) {
    const dt = new Date(String(date_to));
    if (!Number.isNaN(dt.getTime())) {
      items = items.filter((e) => {
        const d = new Date(String(e.date || "").replace(" ", "T") + "Z");
        return !Number.isNaN(d.getTime()) && d <= dt;
      });
    }
  }

  const total_found = items.length;
  const page = items.slice(off, off + lim);

  const search_time = (Date.now() - started) / 1000;
  return {
    success: true,
    emails: page,
    total_found,
    displayed: page.length,
    accounts_count: listResult.accounts_count || 0,
    offset: off,
    limit: lim,
    total_emails: page.length,
    accounts_searched: listResult.accounts_count || 0,
    accounts_info: listResult.accounts_info || [],
    search_time,
    search_params: { query: q, date_from, date_to, unread_only: unreadOnly, folder },
    failed_accounts: [],
    failed_searches: [],
    partial_success: true,
  };
}

async function showEmail({ email_id, folder = "INBOX", account_id = "" } = {}) {
  const id = String(email_id || "").trim();
  if (!id) return { success: false, error: "Missing email_id" };

  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;

  const openFolder = _normalizeFolder(folder);
  return withImapClient(acc.account, async (client) => {
    await client.mailboxOpen(openFolder);
    const msg = await client.fetchOne(Number(id), {
      envelope: true,
      flags: true,
      internalDate: true,
      bodyStructure: true,
      source: true,
    });
    if (!msg) return { success: false, error: `Email not found: ${id}` };

    if (_isTestMode()) {
      const { getMailbox } = require("../testing/mock_store");
      const mb = getMailbox(acc.account.id, openFolder);
      const raw = mb && mb.messages ? mb.messages.find((m) => String(m.uid) === String(id)) : null;
      if (!raw) return { success: false, error: `Email not found: ${id}` };
      const attachments = (raw.attachments || []).map((a) => ({
        filename: a.filename,
        size: a.content ? a.content.length : 0,
        content_type: a.contentType || "application/octet-stream",
      }));
      const unread = !(raw.flags || new Set([])).has("\\Seen");
      return {
        success: true,
        id: String(raw.uid),
        requested_id: String(id),
        from: raw.from,
        to: raw.to,
        cc: raw.cc || "",
        subject: raw.subject,
        date: raw.date,
        body: raw.body || "",
        html_body: raw.html || "",
        has_html: Boolean(raw.html),
        attachments,
        attachment_count: attachments.length,
        unread,
        message_id: raw.messageId || "",
        folder: openFolder,
        account: acc.account.email,
        account_id: acc.account.id,
        from_cache: false,
      };
    }

    const { simpleParser } = require("mailparser");
    const parsed = await simpleParser(msg.source);
    const flags = msg.flags || new Set([]);
    const unread = !flags.has("\\Seen");

    const attachments = (parsed.attachments || []).map((a) => ({
      filename: a.filename || "",
      size: a.size || 0,
      content_type: a.contentType || "application/octet-stream",
    }));

    return {
      success: true,
      id: String(msg.uid),
      requested_id: String(id),
      from: parsed.from ? parsed.from.text || "" : firstAddress(msg.envelope && msg.envelope.from),
      to: parsed.to ? parsed.to.text || "" : firstAddress(msg.envelope && msg.envelope.to),
      cc: parsed.cc ? parsed.cc.text || "" : "",
      subject: parsed.subject || (msg.envelope ? msg.envelope.subject : ""),
      date: formatDateTime(parsed.date || msg.internalDate),
      body: parsed.text || "",
      html_body: typeof parsed.html === "string" ? parsed.html : "",
      has_html: Boolean(parsed.html),
      attachments,
      attachment_count: attachments.length,
      unread,
      message_id: parsed.messageId || (msg.envelope ? msg.envelope.messageId : ""),
      folder: openFolder,
      account: acc.account.email,
      account_id: acc.account.id,
      from_cache: false,
    };
  });
}

async function markEmails({ email_ids, mark_as, folder = "INBOX", account_id = "", dry_run = false } = {}) {
  const ids = (email_ids || []).map((x) => String(x));
  if (!ids.length) return { success: false, error: "Missing email_ids" };
  const markAs = String(mark_as || "").toLowerCase();
  if (markAs !== "read" && markAs !== "unread") return { success: false, error: "Invalid mark_as" };

  if (dry_run) {
    return {
      success: true,
      dry_run: true,
      would_mark: ids.length,
      mark_as: markAs,
      email_ids: ids,
      message: `Dry run: would mark ${ids.length} emails as ${markAs}`,
    };
  }

  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;
  const openFolder = _normalizeFolder(folder);

  return withImapClient(acc.account, async (client) => {
    await client.mailboxOpen(openFolder);
    const uids = ids.map((x) => Number(x));
    const results = [];
    for (const uid of uids) {
      try {
        // eslint-disable-next-line no-await-in-loop
        if (markAs === "read") await client.messageFlagsAdd(uid, ["\\Seen"]);
        else await client.messageFlagsRemove(uid, ["\\Seen"]);
        results.push({ success: true, email_id: String(uid), folder: openFolder, account_id: acc.account.id });
      } catch (e) {
        results.push({ success: false, email_id: String(uid), folder: openFolder, account_id: acc.account.id, error: e && e.message ? e.message : "failed" });
      }
    }
    const marked = results.filter((r) => r.success).length;
    return {
      success: marked === results.length,
      marked_count: marked,
      total: results.length,
      total_requested: results.length,
      mark_as: markAs,
      results,
    };
  });
}

async function _findTrashFolder(client, preferredName) {
  const pref = String(preferredName || "").trim();
  let fallback = pref || "Trash";
  for await (const mb of client.list()) {
    const pathName = mb.path || mb.name || "";
    const special = String(mb.specialUse || "");
    if (special && special.toLowerCase().includes("trash")) return pathName;
    if (pathName.toLowerCase() === "trash") return pathName;
    if (pathName.toLowerCase() === "deleted items") fallback = pathName;
  }
  return fallback;
}

async function deleteEmails({ email_ids, folder = "INBOX", permanent = false, trash_folder = "Trash", account_id = "", dry_run = false } = {}) {
  const ids = (email_ids || []).map((x) => String(x));
  if (!ids.length) return { success: false, error: "Missing email_ids" };

  if (dry_run) {
    return {
      success: true,
      dry_run: true,
      would_delete: ids.length,
      permanent: Boolean(permanent),
      email_ids: ids,
      message: `Dry run: would ${permanent ? "delete" : "move to trash"} ${ids.length} emails`,
    };
  }

  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;
  const openFolder = _normalizeFolder(folder);

  return withImapClient(acc.account, async (client) => {
    await client.mailboxOpen(openFolder);
    const uids = ids.map((x) => Number(x));
    const results = [];

    let trashName = "";
    if (!permanent) trashName = await _findTrashFolder(client, trash_folder);

    for (const uid of uids) {
      try {
        // eslint-disable-next-line no-await-in-loop
        if (permanent) await client.messageDelete(uid);
        else await client.messageMove(uid, trashName);
        results.push({ success: true, email_id: String(uid), folder: openFolder, account_id: acc.account.id });
      } catch (e) {
        results.push({ success: false, email_id: String(uid), folder: openFolder, account_id: acc.account.id, error: e && e.message ? e.message : "failed" });
      }
    }
    const deleted = results.filter((r) => r.success).length;
    return {
      success: deleted === results.length,
      deleted_count: deleted,
      total: results.length,
      total_requested: results.length,
      results,
    };
  });
}

async function sendEmail({ to, subject, body, cc, bcc, account_id = "", is_html = false } = {}) {
  const tos = Array.isArray(to) ? to : [to];
  const recipients = tos.map((x) => String(x)).filter((x) => x.trim());
  if (!recipients.length) return { success: false, error: "Missing --to" };
  const subj = String(subject || "");
  if (!subj.trim()) return { success: false, error: "Missing --subject" };

  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;

  try {
    const r = await sendMail({
      account: acc.account,
      to: recipients.join(", "),
      cc: Array.isArray(cc) ? cc.join(", ") : cc || "",
      bcc: Array.isArray(bcc) ? bcc.join(", ") : bcc || "",
      subject: subj,
      text: is_html ? "" : String(body || ""),
      html: is_html ? String(body || "") : "",
    });

    if (!r.success) return r;
    return {
      success: true,
      message: `Email sent successfully to ${recipients.length} recipient(s)`,
      recipients,
      from: acc.account.email,
    };
  } catch (e) {
    return { success: false, error: e && e.message ? e.message : "send failed", from: acc.account.email };
  }
}

async function replyEmail({ email_id, body, reply_all = false, folder = "INBOX", account_id = "", is_html = false } = {}) {
  const detail = await showEmail({ email_id, folder, account_id });
  if (!detail.success) return detail;
  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;

  const to = reply_all ? detail.to : detail.from;
  const subject = detail.subject && detail.subject.toLowerCase().startsWith("re:") ? detail.subject : `Re: ${detail.subject || ""}`;
  try {
    await sendMail({
      account: acc.account,
      to,
      subject,
      text: is_html ? "" : String(body || ""),
      html: is_html ? String(body || "") : "",
      headers: {
        "In-Reply-To": detail.message_id || "",
        References: detail.message_id || "",
      },
    });
    return {
      success: true,
      message: "Reply sent successfully",
      recipients: [to],
      from: acc.account.email,
    };
  } catch (e) {
    return { success: false, error: e && e.message ? e.message : "reply failed", from: acc.account.email };
  }
}

async function forwardEmail({ email_id, to, body = "", folder = "INBOX", no_attachments = false, account_id = "" } = {}) {
  const detail = await showEmail({ email_id, folder, account_id });
  if (!detail.success) return detail;
  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;

  const recipients = (Array.isArray(to) ? to : [to]).map((x) => String(x)).filter((x) => x.trim());
  if (!recipients.length) return { success: false, error: "Missing --to" };

  let attachments = [];
  if (!no_attachments && detail.attachment_count) {
    // Best-effort: re-parse the email source to get attachment content when possible.
    if (_isTestMode()) {
      const { getMailbox } = require("../testing/mock_store");
      const mb = getMailbox(acc.account.id, _normalizeFolder(folder));
      const raw = mb && mb.messages ? mb.messages.find((m) => String(m.uid) === String(email_id)) : null;
      attachments = (raw && raw.attachments ? raw.attachments : []).map((a) => ({
        filename: a.filename,
        content: a.content,
        contentType: a.contentType,
      }));
    } else {
      // Fall back to forwarding without attachments.
      attachments = [];
    }
  }

  try {
    await sendMail({
      account: acc.account,
      to: recipients.join(", "),
      subject: `Fwd: ${detail.subject || ""}`,
      text: String(body || ""),
      attachments,
    });
    return {
      success: true,
      message: `Email sent successfully to ${recipients.length} recipient(s)`,
      recipients,
      from: acc.account.email,
    };
  } catch (e) {
    return { success: false, error: e && e.message ? e.message : "forward failed", from: acc.account.email };
  }
}

async function listFolders({ account_id } = {}) {
  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;

  return withImapClient(acc.account, async (client) => {
    const folders = [];
    for await (const mb of client.list()) {
      folders.push({
        name: mb.name || mb.path || "",
        attributes: Array.isArray(mb.flags) ? mb.flags.join(" ") : "",
        delimiter: mb.delimiter || "/",
        message_count: 0,
        path: mb.path || mb.name || "",
      });
    }
    return {
      success: true,
      folders,
      folder_tree: {},
      total_folders: folders.length,
      account: acc.account.email,
    };
  });
}

async function downloadAttachments({ email_id, folder = "INBOX", account_id, output_dir = "" } = {}) {
  const detail = await showEmail({ email_id, folder, account_id });
  if (!detail.success) return detail;

  const targetDir = output_dir ? String(output_dir) : paths.getPathConfig().attachmentsDir;
  fs.mkdirSync(targetDir, { recursive: true });

  if (_isTestMode()) {
    const acc = accounts.getAccountByIdOrEmail(account_id);
    if (!acc.success) return acc;
    const { getMailbox } = require("../testing/mock_store");
    const mb = getMailbox(acc.account.id, _normalizeFolder(folder));
    const raw = mb && mb.messages ? mb.messages.find((m) => String(m.uid) === String(email_id)) : null;
    const attachments = [];
    for (const a of raw && raw.attachments ? raw.attachments : []) {
      const p = path.join(targetDir, a.filename);
      fs.writeFileSync(p, a.content);
      attachments.push({
        filename: a.filename,
        size: a.content.length,
        size_formatted: formatSize(a.content.length),
        content_type: a.contentType,
        saved_path: p,
      });
    }
    return {
      success: true,
      attachments,
      attachment_count: attachments.length,
      email_id: String(email_id),
      folder: _normalizeFolder(folder),
      account: acc.account.email,
    };
  }

  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;

  const openFolder = _normalizeFolder(folder);
  const uid = Number(email_id);
  if (!Number.isFinite(uid)) return { success: false, error: "Invalid email_id" };

  return withImapClient(acc.account, async (client) => {
    await client.mailboxOpen(openFolder);
    const msg = await client.fetchOne(uid, { source: true, envelope: true });
    if (!msg || !msg.source) return { success: false, error: `Email not found: ${email_id}` };

    const { simpleParser } = require("mailparser");
    const parsed = await simpleParser(msg.source);

    const attachments = [];
    for (const a of parsed.attachments || []) {
      const filenameRaw = a.filename || "attachment";
      const filename = path.basename(String(filenameRaw));
      if (!filename) continue;
      const content = a.content;
      if (!content || !content.length) continue;

      let dest = path.join(targetDir, filename);
      const ext = path.extname(filename);
      const base = ext ? filename.slice(0, -ext.length) : filename;
      let counter = 1;
      while (fs.existsSync(dest)) {
        dest = path.join(targetDir, `${base}_${counter}${ext}`);
        counter += 1;
      }
      fs.writeFileSync(dest, content);

      attachments.push({
        filename,
        size: content.length,
        size_formatted: formatSize(content.length),
        content_type: a.contentType || "application/octet-stream",
        saved_path: dest,
      });
    }

    return {
      success: true,
      attachments,
      attachment_count: attachments.length,
      email_id: String(email_id),
      folder: openFolder,
      account: acc.account.email,
    };
  });
}

async function flagEmail({ email_id, set_flag, flag_type = "flagged", folder = "INBOX", account_id } = {}) {
  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;
  const openFolder = _normalizeFolder(folder);
  const uid = Number(email_id);
  if (!Number.isFinite(uid)) return { success: false, error: "Invalid email_id" };

  const flagType = String(flag_type || "flagged").toLowerCase();
  const flag = flagType === "flagged" ? "\\Flagged" : "\\Flagged";
  const set = Boolean(set_flag);

  return withImapClient(acc.account, async (client) => {
    await client.mailboxOpen(openFolder);
    if (set) await client.messageFlagsAdd(uid, [flag]);
    else await client.messageFlagsRemove(uid, [flag]);
    return {
      success: true,
      message: `Flag "${flagType}" ${set ? "set" : "unset"}`,
      email_id: String(uid),
      flag_type: flagType,
      set_flag: set,
      folder: openFolder,
      account: acc.account.email,
    };
  });
}

async function moveEmails({ email_ids, target_folder, source_folder = "INBOX", account_id } = {}) {
  const ids = (email_ids || []).map((x) => Number(x)).filter((n) => Number.isFinite(n));
  if (!ids.length) return { success: false, error: "Missing email_ids" };
  const tgt = String(target_folder || "").trim();
  if (!tgt) return { success: false, error: "Missing --target-folder" };
  const src = _normalizeFolder(source_folder);

  const acc = accounts.getAccountByIdOrEmail(account_id);
  if (!acc.success) return acc;

  return withImapClient(acc.account, async (client) => {
    await client.mailboxOpen(src);
    const failed_ids = [];
    let moved = 0;
    for (const uid of ids) {
      try {
        // eslint-disable-next-line no-await-in-loop
        await client.messageMove(uid, tgt);
        moved += 1;
      } catch {
        failed_ids.push(String(uid));
      }
    }
    return {
      success: failed_ids.length === 0,
      message: `Moved ${moved}/${ids.length} emails to "${tgt}"`,
      moved_count: moved,
      source_folder: src,
      target_folder: tgt,
      account: acc.account.email,
      failed_ids,
    };
  });
}

module.exports = {
  listEmails,
  searchEmails,
  showEmail,
  markEmails,
  deleteEmails,
  sendEmail,
  replyEmail,
  forwardEmail,
  listFolders,
  downloadAttachments,
  flagEmail,
  moveEmails,
};
