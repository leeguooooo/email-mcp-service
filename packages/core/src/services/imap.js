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

module.exports = {
  withImapClient,
};
