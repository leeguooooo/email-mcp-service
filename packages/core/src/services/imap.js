function _isTestMode() {
  return String(process.env.MAILBOX_TEST_MODE || "").trim() === "1";
}

async function withImapClient(account, fn) {
  if (_isTestMode()) {
    const { createMockImapClient } = require("../testing/mock_imap_client");
    const client = createMockImapClient(account);
    return fn(client);
  }

  const { ImapFlow } = require("imapflow");
  const client = new ImapFlow({
    host: account.imap.host,
    port: account.imap.port,
    secure: Boolean(account.imap.secure),
    auth: {
      user: account.email,
      pass: account.password,
    },
    logger: false,
  });

  await client.connect();
  try {
    return await fn(client);
  } finally {
    try {
      await client.logout();
    } catch {
      // ignore
    }
  }
}

async function testConnection(account, folder) {
  const openFolder = String(folder || "INBOX") || "INBOX";
  return withImapClient(account, async (client) => {
    const lock = typeof client.getMailboxLock === "function" ? await client.getMailboxLock(openFolder) : null;
    try {
      if (typeof client.mailboxOpen === "function") {
        // Ensure mailbox is selected and mailbox stats are updated.
        // eslint-disable-next-line no-await-in-loop
        await client.mailboxOpen(openFolder);
      }

      const mb = client.mailbox || {};
      const total = Number(mb.exists || 0);
      const unseen = Number(mb.unseen || 0);
      return { success: true, total_emails: total, unread_emails: unseen };
    } finally {
      if (lock && typeof lock.release === "function") lock.release();
    }
  });
}

module.exports = {
  withImapClient,
  testConnection,
};
