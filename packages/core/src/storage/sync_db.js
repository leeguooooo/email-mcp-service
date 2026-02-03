const fs = require("fs");
const path = require("path");

// Use asm.js build to avoid shipping wasm assets.
const initSqlJs = require("sql.js/dist/sql-asm.js");

let _sqlPromise = null;

async function _getSQL() {
  if (!_sqlPromise) _sqlPromise = initSqlJs();
  return _sqlPromise;
}

function _readDbFile(dbPath) {
  try {
    if (!fs.existsSync(dbPath)) return null;
    const buf = fs.readFileSync(dbPath);
    return new Uint8Array(buf);
  } catch {
    return null;
  }
}

function _writeDbFile(dbPath, bytes) {
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  fs.writeFileSync(dbPath, Buffer.from(bytes));
}

function _ensureSchema(db) {
  // Matches Python schema in src/database/email_sync_db.py
  db.run(`
    CREATE TABLE IF NOT EXISTS accounts (
      id TEXT PRIMARY KEY,
      email TEXT UNIQUE NOT NULL,
      provider TEXT NOT NULL,
      last_sync TIMESTAMP,
      total_emails INTEGER DEFAULT 0,
      sync_status TEXT DEFAULT 'never',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS folders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      account_id TEXT NOT NULL,
      name TEXT NOT NULL,
      display_name TEXT,
      message_count INTEGER DEFAULT 0,
      unread_count INTEGER DEFAULT 0,
      last_sync TIMESTAMP,
      FOREIGN KEY (account_id) REFERENCES accounts (id),
      UNIQUE(account_id, name)
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS emails (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      account_id TEXT NOT NULL,
      folder_id INTEGER NOT NULL,
      uid TEXT NOT NULL,
      message_id TEXT,
      subject TEXT,
      sender TEXT,
      sender_email TEXT,
      recipients TEXT,
      date_sent TIMESTAMP,
      date_received TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      is_read BOOLEAN DEFAULT FALSE,
      is_flagged BOOLEAN DEFAULT FALSE,
      is_deleted BOOLEAN DEFAULT FALSE,
      has_attachments BOOLEAN DEFAULT FALSE,
      size_bytes INTEGER DEFAULT 0,
      content_hash TEXT,
      sync_status TEXT DEFAULT 'synced',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (account_id) REFERENCES accounts (id),
      FOREIGN KEY (folder_id) REFERENCES folders (id),
      UNIQUE(account_id, folder_id, uid)
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS email_content (
      email_id INTEGER PRIMARY KEY,
      plain_text TEXT,
      html_text TEXT,
      headers TEXT,
      raw_size INTEGER,
      content_loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (email_id) REFERENCES emails (id) ON DELETE CASCADE
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS attachments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email_id INTEGER NOT NULL,
      filename TEXT,
      content_type TEXT,
      size_bytes INTEGER DEFAULT 0,
      content_id TEXT,
      is_inline BOOLEAN DEFAULT FALSE,
      data BLOB,
      file_path TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (email_id) REFERENCES emails (id) ON DELETE CASCADE
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS sync_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      account_id TEXT NOT NULL,
      folder_name TEXT,
      sync_type TEXT,
      start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      end_time TIMESTAMP,
      emails_added INTEGER DEFAULT 0,
      emails_updated INTEGER DEFAULT 0,
      emails_deleted INTEGER DEFAULT 0,
      status TEXT DEFAULT 'running',
      error_message TEXT,
      FOREIGN KEY (account_id) REFERENCES accounts (id)
    );
  `);

  const indexes = [
    "CREATE INDEX IF NOT EXISTS idx_emails_account_folder ON emails (account_id, folder_id)",
    "CREATE INDEX IF NOT EXISTS idx_emails_uid ON emails (uid)",
    "CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails (message_id)",
    "CREATE INDEX IF NOT EXISTS idx_emails_date_sent ON emails (date_sent)",
    "CREATE INDEX IF NOT EXISTS idx_emails_is_read ON emails (is_read)",
    "CREATE INDEX IF NOT EXISTS idx_emails_is_flagged ON emails (is_flagged)",
    "CREATE INDEX IF NOT EXISTS idx_emails_subject ON emails (subject)",
    "CREATE INDEX IF NOT EXISTS idx_emails_sender_email ON emails (sender_email)",
    "CREATE INDEX IF NOT EXISTS idx_folders_account ON folders (account_id)",
    "CREATE INDEX IF NOT EXISTS idx_sync_history_account ON sync_history (account_id)",
    "CREATE INDEX IF NOT EXISTS idx_attachments_email ON attachments (email_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_emails_account_folder_uid ON emails (account_id, folder_id, uid)",
  ];
  for (const sql of indexes) db.run(sql);
}

function _execScalar(db, sql, params) {
  const stmt = db.prepare(sql);
  try {
    if (params) stmt.bind(params);
    if (!stmt.step()) return null;
    const row = stmt.get();
    return row && row.length ? row[0] : null;
  } finally {
    stmt.free();
  }
}

function _execRows(db, sql, params) {
  const stmt = db.prepare(sql);
  try {
    if (params) stmt.bind(params);
    const cols = stmt.getColumnNames();
    const rows = [];
    while (stmt.step()) {
      const values = stmt.get();
      const obj = {};
      for (let i = 0; i < cols.length; i += 1) obj[cols[i]] = values[i];
      rows.push(obj);
    }
    return rows;
  } finally {
    stmt.free();
  }
}

async function openSyncDb(dbPath) {
  const SQL = await _getSQL();
  const data = _readDbFile(dbPath);
  const db = data ? new SQL.Database(data) : new SQL.Database();
  _ensureSchema(db);
  return {
    db,
    flush() {
      const bytes = db.export();
      _writeDbFile(dbPath, bytes);
    },
    close() {
      db.close();
    },
  };
}

async function listEmailsFromCache({ dbPath, accountId, folder, unreadOnly, limit, offset, dateFrom, dateTo }) {
  if (!dbPath || !fs.existsSync(dbPath)) return null;

  const h = await openSyncDb(dbPath);
  try {
    const f = String(folder || "all");
    const resolvedFolder = f && f !== "all" ? f : "all";

    let query = `
      SELECT DISTINCT
        e.uid as id,
        e.uid as uid,
        e.message_id as message_id,
        e.subject,
        e.sender_email as "from",
        e.date_sent as date,
        e.is_read as is_read,
        e.has_attachments as has_attachments,
        e.account_id as account_id,
        COALESCE(a.email, e.account_id) as account,
        CASE WHEN e.folder_id IS NULL THEN 'INBOX' ELSE f.name END as folder
      FROM emails e
      LEFT JOIN accounts a ON e.account_id = a.id
      LEFT JOIN folders f ON e.folder_id = f.id
      WHERE e.is_deleted = 0
    `;

    const params = [];
    if (accountId) {
      query += " AND e.account_id = ?";
      params.push(String(accountId));
    }
    if (resolvedFolder !== "all") {
      query += " AND (f.name = ? COLLATE NOCASE OR (e.folder_id IS NULL AND ? = 'INBOX'))";
      params.push(resolvedFolder);
      params.push(resolvedFolder);
    }
    if (unreadOnly) {
      query += " AND e.is_read = 0";
    }
    if (dateFrom) {
      query += " AND e.date_sent >= ?";
      params.push(String(dateFrom));
    }
    if (dateTo) {
      query += " AND e.date_sent <= ?";
      params.push(String(dateTo));
    }

    // totals (same filters, no limit)
    const totalSql = `SELECT COUNT(*) FROM (${query})`;
    const unreadSql = `SELECT COUNT(*) FROM (${query} AND is_read = 0)`;

    query += " ORDER BY e.date_sent DESC LIMIT ? OFFSET ?";
    params.push(Number(limit));
    params.push(Number(offset));

    const rows = _execRows(h.db, query, params);
    const emails = rows.map((row) => ({
      id: String(row.id),
      uid: String(row.uid),
      message_id: row.message_id || "",
      subject: row.subject || "No Subject",
      from: row.from || "",
      date: row.date || "",
      unread: !row.is_read,
      has_attachments: Boolean(row.has_attachments),
      account: row.account || "",
      account_id: row.account_id || "",
      folder: row.folder || "INBOX",
      source: "cache_sync_db",
    }));

    const total_in_folder = Number(_execScalar(h.db, totalSql, params.slice(0, -2)) || emails.length);
    const unread_count = Number(_execScalar(h.db, unreadSql, params.slice(0, -2)) || emails.filter((e) => e.unread).length);

    return {
      success: true,
      emails,
      total_in_folder,
      unread_count,
      offset: Number(offset),
      limit: Number(limit),
      from_cache: true,
    };
  } catch {
    return null;
  } finally {
    try {
      h.close();
    } catch {
      // ignore
    }
  }
}

async function upsertAccount({ dbPath, id, email, provider }) {
  const h = await openSyncDb(dbPath);
  try {
    h.db.run(
      "INSERT OR REPLACE INTO accounts (id, email, provider, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
      [String(id), String(email), String(provider)]
    );
    h.flush();
    return { success: true };
  } catch (e) {
    return { success: false, error: e && e.message ? e.message : "db error" };
  } finally {
    h.close();
  }
}

async function upsertFolder({ dbPath, accountId, name, displayName, messageCount, unreadCount, lastSyncIso }) {
  const h = await openSyncDb(dbPath);
  try {
    // Keep the Python semantics: do NOT use REPLACE because it breaks folder_id.
    h.db.run(
      `
        INSERT INTO folders (account_id, name, display_name, message_count, unread_count, last_sync)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(account_id, name) DO UPDATE SET
          display_name = excluded.display_name,
          message_count = excluded.message_count,
          unread_count = excluded.unread_count,
          last_sync = excluded.last_sync
      `,
      [
        String(accountId),
        String(name),
        String(displayName || name),
        Number(messageCount || 0),
        Number(unreadCount || 0),
        String(lastSyncIso || new Date().toISOString()),
      ]
    );
    const folderId = _execScalar(
      h.db,
      "SELECT id FROM folders WHERE account_id = ? AND name = ?",
      [String(accountId), String(name)]
    );
    h.flush();
    return { success: true, folderId: Number(folderId) };
  } catch (e) {
    return { success: false, error: e && e.message ? e.message : "db error" };
  } finally {
    h.close();
  }
}

async function upsertEmails({ dbPath, accountId, folderId, emails }) {
  const h = await openSyncDb(dbPath);
  try {
    const stmt = h.db.prepare(
      `
        INSERT OR REPLACE INTO emails (
          account_id, folder_id, uid, message_id, subject, sender, sender_email, recipients,
          date_sent, is_read, is_flagged, is_deleted, has_attachments, size_bytes, sync_status, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', CURRENT_TIMESTAMP)
      `
    );
    try {
      for (const e of emails || []) {
        const uid = String(e.uid || e.id || "").trim();
        if (!uid) continue;
        const isRead = e.unread ? 0 : 1;
        stmt.run([
          String(accountId),
          Number(folderId),
          uid,
          String(e.message_id || ""),
          String(e.subject || ""),
          String(e.from || ""),
          String(e.from || ""),
          JSON.stringify({ to: e.to || "", cc: e.cc || "" }),
          String(e.date || ""),
          isRead,
          0,
          0,
          e.has_attachments ? 1 : 0,
          Number(e.size_bytes || e.size || 0),
        ]);
      }
    } finally {
      stmt.free();
    }
    h.flush();
    return { success: true };
  } catch (e) {
    return { success: false, error: e && e.message ? e.message : "db error" };
  } finally {
    h.close();
  }
}

module.exports = {
  listEmailsFromCache,
  upsertAccount,
  upsertFolder,
  upsertEmails,
};
