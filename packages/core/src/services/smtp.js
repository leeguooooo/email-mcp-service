function _isTestMode() {
  return String(process.env.MAILBOX_TEST_MODE || "").trim() === "1";
}

async function testConnection(account) {
  if (_isTestMode()) {
    return { success: true };
  }

  if (!account || !account.smtp || !account.smtp.host) {
    return { success: false, error: "Missing SMTP host" };
  }

  const nodemailer = require("nodemailer");
  const transporter = nodemailer.createTransport({
    host: account.smtp.host,
    port: account.smtp.port,
    secure: Boolean(account.smtp.secure),
    auth: {
      user: account.email,
      pass: account.password,
    },
  });

  try {
    await transporter.verify();
    return { success: true };
  } catch (e) {
    return { success: false, error: e && e.message ? e.message : "SMTP verify failed" };
  }
}

async function sendMail({ account, to, cc, bcc, subject, text, html, attachments, headers }) {
  if (_isTestMode()) {
    return {
      success: true,
      messageId: "<mock-sent@example.com>",
    };
  }

  const nodemailer = require("nodemailer");
  const transporter = nodemailer.createTransport({
    host: account.smtp.host,
    port: account.smtp.port,
    secure: Boolean(account.smtp.secure),
    auth: {
      user: account.email,
      pass: account.password,
    },
  });

  const info = await transporter.sendMail({
    from: account.email,
    to,
    cc,
    bcc,
    subject,
    text,
    html,
    attachments,
    headers,
  });

  return {
    success: true,
    messageId: info.messageId || "",
  };
}

module.exports = {
  sendMail,
  testConnection,
};
