const { getMailbox, listMailboxNames } = require("./mock_store");

function _cloneMessage(m) {
  return {
    uid: m.uid,
    envelope: {
      subject: m.subject,
      from: [{ address: m.from }],
      to: [{ address: m.to }],
      cc: m.cc ? [{ address: m.cc }] : [],
      messageId: m.messageId,
      date: new Date(m.date.replace(" ", "T") + "Z"),
    },
    flags: new Set([...m.flags]),
    internalDate: new Date(m.date.replace(" ", "T") + "Z"),
    source: Buffer.from(
      [
        `Message-ID: ${m.messageId}`,
        `From: ${m.from}`,
        `To: ${m.to}`,
        `Subject: ${m.subject}`,
        `Date: ${m.date}`,
        "",
        m.body || "",
      ].join("\n")
    ),
    bodyStructure: {
      childNodes: (m.attachments || []).map((a) => ({
        disposition: "attachment",
        parameters: { filename: a.filename },
        type: (a.contentType || "application/octet-stream").split("/")[0],
        subtype: (a.contentType || "application/octet-stream").split("/")[1],
      })),
    },
  };
}

class MockImapClient {
  constructor(account) {
    this._account = account;
    this._mailbox = "INBOX";
  }

  async mailboxOpen(name) {
    this._mailbox = name || "INBOX";
    const mb = getMailbox(this._account.id, this._mailbox);
    if (!mb) throw new Error(`Mailbox not found: ${this._mailbox}`);
    const messages = mb.messages || [];
    const unseen = messages.filter((m) => !m.flags.has("\\Seen")).length;
    return { path: this._mailbox, exists: messages.length, unseen };
  }

  async search(query) {
    const mb = getMailbox(this._account.id, this._mailbox);
    if (!mb) throw new Error(`Mailbox not found: ${this._mailbox}`);
    const messages = mb.messages || [];

    const wantsUnseen = Array.isArray(query) ? query.includes("UNSEEN") : false;
    const list = wantsUnseen ? messages.filter((m) => !m.flags.has("\\Seen")) : messages;
    return list.map((m) => m.uid);
  }

  async *fetch(uids, opts) {
    const mb = getMailbox(this._account.id, this._mailbox);
    if (!mb) throw new Error(`Mailbox not found: ${this._mailbox}`);
    const set = new Set(Array.isArray(uids) ? uids : [uids]);
    for (const m of mb.messages || []) {
      if (!set.has(m.uid)) continue;
      const msg = _cloneMessage(m);
      // mimic imapflow fetch response shape
      const out = { uid: msg.uid };
      if (opts.envelope) out.envelope = msg.envelope;
      if (opts.flags) out.flags = msg.flags;
      if (opts.internalDate) out.internalDate = msg.internalDate;
      if (opts.bodyStructure) out.bodyStructure = msg.bodyStructure;
      if (opts.source) out.source = msg.source;
      yield out;
    }
  }

  async fetchOne(uid, opts) {
    const mb = getMailbox(this._account.id, this._mailbox);
    if (!mb) throw new Error(`Mailbox not found: ${this._mailbox}`);
    const m = (mb.messages || []).find((x) => x.uid === Number(uid));
    if (!m) return null;
    const msg = _cloneMessage(m);
    const out = { uid: msg.uid };
    if (opts.envelope) out.envelope = msg.envelope;
    if (opts.flags) out.flags = msg.flags;
    if (opts.internalDate) out.internalDate = msg.internalDate;
    if (opts.bodyStructure) out.bodyStructure = msg.bodyStructure;
    if (opts.source) out.source = msg.source;
    return out;
  }

  async messageFlagsAdd(uids, flags) {
    const mb = getMailbox(this._account.id, this._mailbox);
    if (!mb) throw new Error(`Mailbox not found: ${this._mailbox}`);
    const set = new Set(Array.isArray(uids) ? uids.map(Number) : [Number(uids)]);
    for (const m of mb.messages || []) {
      if (!set.has(m.uid)) continue;
      for (const f of flags) m.flags.add(f);
    }
  }

  async messageFlagsRemove(uids, flags) {
    const mb = getMailbox(this._account.id, this._mailbox);
    if (!mb) throw new Error(`Mailbox not found: ${this._mailbox}`);
    const set = new Set(Array.isArray(uids) ? uids.map(Number) : [Number(uids)]);
    for (const m of mb.messages || []) {
      if (!set.has(m.uid)) continue;
      for (const f of flags) m.flags.delete(f);
    }
  }

  async messageMove(uids, target) {
    const src = getMailbox(this._account.id, this._mailbox);
    const dst = getMailbox(this._account.id, target);
    if (!src) throw new Error(`Mailbox not found: ${this._mailbox}`);
    if (!dst) throw new Error(`Target mailbox not found: ${target}`);
    const set = new Set(Array.isArray(uids) ? uids.map(Number) : [Number(uids)]);
    const keep = [];
    for (const m of src.messages || []) {
      if (set.has(m.uid)) {
        dst.messages.push(m);
      } else {
        keep.push(m);
      }
    }
    src.messages = keep;
  }

  async messageDelete(uids) {
    const src = getMailbox(this._account.id, this._mailbox);
    if (!src) throw new Error(`Mailbox not found: ${this._mailbox}`);
    const set = new Set(Array.isArray(uids) ? uids.map(Number) : [Number(uids)]);
    src.messages = (src.messages || []).filter((m) => !set.has(m.uid));
  }

  async *list() {
    const names = listMailboxNames(this._account.id);
    for (const name of names) {
      yield {
        path: name,
        name,
        delimiter: "/",
        flags: new Set([]),
        specialUse: name.toLowerCase() === "trash" ? "\\Trash" : "",
      };
    }
  }
}

function createMockImapClient(account) {
  return new MockImapClient(account);
}

module.exports = {
  createMockImapClient,
};
