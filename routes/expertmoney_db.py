"""ExpertMoney DB helpers — integrado ao banco empenhos.db do Cerebro."""
import sqlite3
import json
import os
import copy
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "/app/empenhos.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS em_accounts (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    agency     TEXT,
    number     TEXT NOT NULL,
    bank       TEXT DEFAULT 'Banco do Brasil',
    notes      TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS em_analysis_sessions (
    id              TEXT PRIMARY KEY,
    account_id      TEXT REFERENCES em_accounts(id) ON DELETE CASCADE,
    analyzed_at     TEXT DEFAULT (datetime('now','localtime')),
    period_start    TEXT,
    period_end      TEXT,
    file_count      INTEGER DEFAULT 0,
    tx_count        INTEGER DEFAULT 0,
    invest_count    INTEGER DEFAULT 0,
    alert_count     INTEGER DEFAULT 0,
    critical_count  INTEGER DEFAULT 0,
    warning_count   INTEGER DEFAULT 0,
    info_count      INTEGER DEFAULT 0,
    flagged_count   INTEGER DEFAULT 0,
    total_credits   REAL DEFAULT 0,
    total_debits    REAL DEFAULT 0,
    total_rendimento REAL DEFAULT 0,
    last_balance    REAL DEFAULT 0,
    last_period     TEXT,
    stats_json      TEXT
);

CREATE TABLE IF NOT EXISTS em_alerts (
    id              TEXT PRIMARY KEY,
    session_id      TEXT REFERENCES em_analysis_sessions(id) ON DELETE CASCADE,
    account_id      TEXT REFERENCES em_accounts(id) ON DELETE CASCADE,
    severity        TEXT NOT NULL,
    category        TEXT,
    title           TEXT,
    description     TEXT,
    evidence_json   TEXT,
    related_ids     TEXT,
    resolved        INTEGER DEFAULT 0,
    resolved_at     TEXT,
    resolved_by     TEXT,
    resolution_note TEXT,
    correlated_with TEXT,
    merged_into     TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS em_transactions_log (
    id          TEXT,
    session_id  TEXT REFERENCES em_analysis_sessions(id) ON DELETE CASCADE,
    account_id  TEXT,
    type        TEXT,
    date        TEXT,
    date_str    TEXT,
    amount      REAL,
    memo        TEXT,
    period      TEXT,
    flagged     INTEGER DEFAULT 0,
    flags_json  TEXT,
    PRIMARY KEY (id, session_id)
);

CREATE TABLE IF NOT EXISTS em_alert_attachments (
    id          TEXT PRIMARY KEY,
    alert_id    TEXT REFERENCES em_alerts(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    mimetype    TEXT,
    size        INTEGER,
    stored_name TEXT,
    note        TEXT,
    uploaded_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS em_detector_config (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    TEXT REFERENCES em_accounts(id) ON DELETE CASCADE,
    config_key    TEXT NOT NULL,
    config_value  REAL NOT NULL,
    updated_at    TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_em_sessions_account ON em_analysis_sessions(account_id);
CREATE INDEX IF NOT EXISTS idx_em_alerts_session   ON em_alerts(session_id);
CREATE INDEX IF NOT EXISTS idx_em_alerts_account   ON em_alerts(account_id);
CREATE INDEX IF NOT EXISTS idx_em_txlog_session    ON em_transactions_log(session_id);
CREATE INDEX IF NOT EXISTS idx_em_attachments_alert ON em_alert_attachments(alert_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_em_detector_config_uniq
    ON em_detector_config (IFNULL(account_id, ''), config_key);
"""

MIGRATIONS = [
    "ALTER TABLE em_alerts ADD COLUMN correlated_with TEXT;",
    "ALTER TABLE em_alerts ADD COLUMN merged_into TEXT;",
]


def get_em_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_expertmoney_tables(app):
    """Cria tabelas do ExpertMoney no banco do Cerebro."""
    conn = app._get_db()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    for migration in MIGRATIONS:
        try:
            conn.execute(migration)
            conn.commit()
        except Exception:
            pass
    print("[OK] Tabelas ExpertMoney inicializadas no banco do Cerebro.")


def save_em_session(session: dict, alerts: list, transactions: list) -> None:
    conn = get_em_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO em_analysis_sessions
                  (id,account_id,period_start,period_end,file_count,tx_count,invest_count,
                   alert_count,critical_count,warning_count,info_count,flagged_count,
                   total_credits,total_debits,total_rendimento,last_balance,last_period,stats_json)
                VALUES
                  (:id,:account_id,:period_start,:period_end,:file_count,:tx_count,:invest_count,
                   :alert_count,:critical_count,:warning_count,:info_count,:flagged_count,
                   :total_credits,:total_debits,:total_rendimento,:last_balance,:last_period,:stats_json)
            """, session)
            for a in alerts:
                conn.execute("""
                    INSERT INTO em_alerts
                      (id,session_id,account_id,severity,category,title,description,
                       evidence_json,related_ids,resolved,resolved_at,resolved_by,
                       resolution_note,correlated_with,merged_into)
                    VALUES
                      (:id,:session_id,:account_id,:severity,:category,:title,:description,
                       :evidence_json,:related_ids,:resolved,:resolved_at,:resolved_by,
                       :resolution_note,:correlated_with,:merged_into)
                """, a)
            for t in transactions:
                conn.execute("""
                    INSERT OR IGNORE INTO em_transactions_log
                      (id,session_id,account_id,type,date,date_str,amount,memo,period,flagged,flags_json)
                    VALUES
                      (:id,:session_id,:account_id,:type,:date,:date_str,:amount,:memo,:period,:flagged,:flags_json)
                """, t)
    finally:
        conn.close()


def get_em_session_with_alerts(conn: sqlite3.Connection, session_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM em_analysis_sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        return None
    session = dict(row)
    session["stats"] = json.loads(session.get("stats_json") or "{}")
    alert_rows = conn.execute(
        "SELECT * FROM em_alerts WHERE session_id=? ORDER BY severity, created_at", (session_id,)
    ).fetchall()
    session["alerts"] = [
        {
            **dict(a),
            "evidence":       json.loads(a["evidence_json"])   if a["evidence_json"]   else [],
            "relatedIds":     json.loads(a["related_ids"])     if a["related_ids"]     else [],
            "correlatedWith": json.loads(a["correlated_with"]) if a["correlated_with"] else [],
            "mergedInto":     a["merged_into"],
        }
        for a in alert_rows
    ]
    return session


def get_em_account_history(conn: sqlite3.Connection, account_id: str) -> list:
    rows = conn.execute(
        "SELECT * FROM em_analysis_sessions WHERE account_id=? ORDER BY analyzed_at DESC", (account_id,)
    ).fetchall()
    return [{**dict(s), "stats": json.loads(s["stats_json"] or "{}")} for s in rows]


def load_em_config(conn: sqlite3.Connection, account_id: Optional[str], default_config: dict) -> dict:
    config = copy.deepcopy(default_config)
    for row in conn.execute("SELECT config_key, config_value FROM em_detector_config WHERE account_id IS NULL").fetchall():
        if row["config_key"] in config:
            config[row["config_key"]] = row["config_value"]
    if account_id:
        for row in conn.execute("SELECT config_key, config_value FROM em_detector_config WHERE account_id=?", (account_id,)).fetchall():
            if row["config_key"] in config:
                config[row["config_key"]] = row["config_value"]
    return config
