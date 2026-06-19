"""ExpertMoney — Blueprint Flask (portado do FastAPI)
Todas as rotas sob /api/extratos/*
"""
import io
import re
import os
import json
import uuid
import math
import shutil
import urllib.request
from datetime import datetime, timezone
from zipfile import ZipFile

from flask import Blueprint, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename

from routes._shared import require_login
from routes.expertmoney_db import (
    get_em_db_connection, save_em_session,
    get_em_session_with_alerts, get_em_account_history, load_em_config
)
from src.parsers.ofx_parser import parse_ofx
from src.parsers.txt_parser import parse_txt
from src.analyzers.detectors import run_analysis, run_cross_account_analysis, CONFIG as DETECTOR_CONFIG
from src.analyzers.search import search_transactions
from src.exporters.report_exporter import build_excel, build_pdf, generate_csv_transactions

bp = Blueprint("expertmoney", __name__)

em_session_cache: dict = {}

UPLOAD_DIR   = os.environ.get("UPLOAD_DIR",   "/app/uploads")
EXTRACTED_DIR = os.environ.get("EXTRACTED_DIR", "/app/extracted")
ATT_DIR      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "attachments")


def date_tag() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def build_ofx_meta(parsed: dict) -> dict:
    txns = parsed.get("transactions", [])
    return {
        "filename": parsed.get("filename", ""),
        "period": parsed.get("period", ""),
        "ledgerBalance": parsed.get("ledgerBalance"),
        "ledgerBalanceDate": parsed.get("ledgerBalanceDate"),
        "dateStart": parsed.get("dateStart"),
        "dateEnd": parsed.get("dateEnd"),
        "txSum": sum(t.get("amount", 0.0) for t in txns),
        "txCount": len(txns),
    }


def normalize_acc_number(num: str) -> str:
    return re.sub(r"[.\s]", "", str(num or "")).lstrip("0").upper()


def get_tx_date(t):
    d = t.get("date")
    if isinstance(d, datetime):
        return d
    try:
        return datetime.fromisoformat(str(d).replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def fmt_brl(v) -> str:
    try:
        return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


def get_em_session_data(session_id: str):
    s = em_session_cache.get(session_id)
    if s and s.get("analyzed"):
        s["createdAt"] = datetime.now()
        return s

    conn = get_em_db_connection()
    try:
        db_sess = get_em_session_with_alerts(conn, session_id)
        if not db_sess:
            return None

        tx_rows = conn.execute("SELECT * FROM em_transactions_log WHERE session_id = ?", (session_id,)).fetchall()
        transactions = []
        for t in tx_rows:
            flags = []
            try:
                if t["flags_json"]:
                    flags = json.loads(t["flags_json"])
            except Exception:
                pass
            transactions.append({
                "id": t["id"], "type": t["type"], "date": t["date"],
                "dateStr": t["date_str"], "amount": t["amount"],
                "memo": t["memo"] or "", "period": t["period"] or "",
                "flagged": t["flagged"] == 1, "flags": flags
            })

        investments = []
        stats = db_sess.get("stats") or {}
        for i in stats.get("monthlyInvestments", []):
            investments.append({
                "period": i.get("period", ""), "periodSort": i.get("periodSort", ""),
                "summary": {
                    "saldoAnterior": i.get("saldoAnterior", 0.0), "aplicacoes": i.get("aplicacoes", 0.0),
                    "resgates": i.get("resgates", 0.0), "rendBruto": i.get("rendBruto", 0.0),
                    "ir": i.get("ir", 0.0), "saldoAtual": i.get("saldoAtual", 0.0)
                },
                "rentability": {"month": i.get("rentMonth", 0.0), "year": i.get("rentYear", 0.0), "y12": i.get("rentY12", 0.0)}
            })

        account = None
        if db_sess.get("account_id"):
            acc_row = conn.execute("SELECT * FROM em_accounts WHERE id = ?", (db_sess["account_id"],)).fetchone()
            if acc_row:
                account = dict(acc_row)

        return {"transactions": transactions, "investments": investments,
                "alerts": db_sess.get("alerts", []), "stats": stats, "account": account}
    finally:
        conn.close()


def _build_db_records(session_id, account, transactions, investments, all_alerts, stats, acc_files):
    periods = stats.get("periods") or []
    db_session = {
        "id": session_id,
        "account_id": account["id"] if account else None,
        "period_start": periods[0] if periods else None,
        "period_end": periods[-1] if periods else None,
        "file_count": len(acc_files),
        "tx_count": len(transactions),
        "invest_count": len(investments),
        "alert_count": len(stats.get("alerts", all_alerts)),
        "critical_count": stats.get("criticalAlerts", 0),
        "warning_count": stats.get("warningAlerts", 0),
        "info_count": stats.get("infoAlerts", 0),
        "flagged_count": stats.get("flaggedCount", 0),
        "total_credits": stats.get("totalCredits", 0.0),
        "total_debits": stats.get("totalDebits", 0.0),
        "total_rendimento": stats.get("totalRendimento", 0.0),
        "last_balance": stats.get("lastBalance", 0.0),
        "last_period": stats.get("lastPeriod", ""),
        "stats_json": json.dumps(stats)
    }
    db_alerts = [{
        "id": a["id"], "session_id": session_id,
        "account_id": account["id"] if account else None,
        "severity": a["severity"], "category": a["category"],
        "title": a["title"], "description": a["description"],
        "evidence_json": json.dumps(a.get("evidence") or []),
        "related_ids": json.dumps(a.get("relatedIds") or []),
        "resolved": 1 if a.get("resolved") else 0,
        "resolved_at": a.get("resolvedAt"), "resolved_by": a.get("resolvedBy"),
        "resolution_note": a.get("resolutionNote"),
        "correlated_with": json.dumps(a.get("correlatedWith") or []),
        "merged_into": a.get("mergedInto")
    } for a in all_alerts]
    db_txns = [{
        "id": t["id"], "session_id": session_id,
        "account_id": account["id"] if account else None,
        "type": t["type"],
        "date": t["date"].isoformat() if isinstance(t["date"], datetime) else t["date"],
        "date_str": t["dateStr"], "amount": t["amount"], "memo": t["memo"],
        "period": t["period"], "flagged": 1 if t.get("flagged") else 0,
        "flags_json": json.dumps(t.get("flags") or [])
    } for t in transactions]
    return db_session, db_alerts, db_txns


# ════════════════════════════════════════════════════════════════
# HEALTH
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/health", methods=["GET"])
@require_login
def em_health():
    conn = get_em_db_connection()
    try:
        accounts = conn.execute("SELECT COUNT(*) FROM em_accounts").fetchone()[0]
        sessions = conn.execute("SELECT COUNT(*) FROM em_analysis_sessions").fetchone()[0]
        return jsonify({"status": "ok", "version": "3.0.0-flask", "accounts": accounts,
                        "sessions": sessions, "cacheSize": len(em_session_cache),
                        "timestamp": datetime.now(tz=timezone.utc).isoformat()})
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# ACCOUNTS CRUD
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/accounts", methods=["GET"])
@require_login
def em_list_accounts():
    conn = get_em_db_connection()
    try:
        rows = conn.execute("SELECT * FROM em_accounts ORDER BY name").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@bp.route("/api/extratos/accounts", methods=["POST"])
@require_login
def em_create_account():
    body = request.get_json(force=True) or {}
    name = (body.get("name") or "").strip()
    number = (body.get("number") or "").strip()
    agency = (body.get("agency") or "").strip()
    bank = (body.get("bank") or "Banco do Brasil").strip()
    notes = (body.get("notes") or "").strip()
    if not name or not number:
        return jsonify({"detail": "name e number são obrigatórios."}), 400
    conn = get_em_db_connection()
    try:
        existing = conn.execute("SELECT * FROM em_accounts WHERE number=? AND bank=?", (number, bank)).fetchone()
        if existing:
            return jsonify({"detail": "Conta já cadastrada.", "account": dict(existing)}), 409
        acc_id = str(uuid.uuid4())
        conn.execute("INSERT INTO em_accounts (id,name,agency,number,bank,notes) VALUES (?,?,?,?,?,?)",
                     (acc_id, name, agency, number, bank, notes))
        conn.commit()
        return jsonify({"id": acc_id, "name": name, "agency": agency, "number": number, "bank": bank, "notes": notes}), 201
    finally:
        conn.close()


@bp.route("/api/extratos/accounts/<acc_id>", methods=["GET"])
@require_login
def em_get_account(acc_id):
    conn = get_em_db_connection()
    try:
        row = conn.execute("SELECT * FROM em_accounts WHERE id=?", (acc_id,)).fetchone()
        if not row:
            return jsonify({"detail": "Conta não encontrada."}), 404
        return jsonify(dict(row))
    finally:
        conn.close()


@bp.route("/api/extratos/accounts/<acc_id>", methods=["PATCH"])
@require_login
def em_update_account(acc_id):
    conn = get_em_db_connection()
    try:
        row = conn.execute("SELECT * FROM em_accounts WHERE id=?", (acc_id,)).fetchone()
        if not row:
            return jsonify({"detail": "Conta não encontrada."}), 404
        body = request.get_json(force=True) or {}
        name  = (body.get("name") or row["name"]).strip()
        agency = (body.get("agency") if body.get("agency") is not None else (row["agency"] or "")).strip()
        bank  = (body.get("bank") or row["bank"]).strip()
        notes = (body.get("notes") if body.get("notes") is not None else (row["notes"] or "")).strip()
        conn.execute("UPDATE em_accounts SET name=?,agency=?,bank=?,notes=?,updated_at=datetime('now','localtime') WHERE id=?",
                     (name, agency, bank, notes, acc_id))
        conn.commit()
        return jsonify(dict(conn.execute("SELECT * FROM em_accounts WHERE id=?", (acc_id,)).fetchone()))
    finally:
        conn.close()


@bp.route("/api/extratos/accounts/<acc_id>", methods=["DELETE"])
@require_login
def em_delete_account(acc_id):
    conn = get_em_db_connection()
    try:
        cur = conn.execute("DELETE FROM em_accounts WHERE id=?", (acc_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"detail": "Conta não encontrada."}), 404
        return jsonify({"deleted": True})
    finally:
        conn.close()


@bp.route("/api/extratos/accounts/<acc_id>/history", methods=["GET"])
@require_login
def em_account_history(acc_id):
    conn = get_em_db_connection()
    try:
        account = conn.execute("SELECT * FROM em_accounts WHERE id=?", (acc_id,)).fetchone()
        if not account:
            return jsonify({"detail": "Conta não encontrada."}), 404
        history = get_em_account_history(conn, acc_id)
        return jsonify({"account": dict(account), "history": history})
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# UPLOAD
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/upload", methods=["POST"])
@require_login
def em_upload():
    session_id = str(uuid.uuid4())
    raw_files = []
    files = request.files.getlist("files")
    if not files:
        return jsonify({"detail": "Nenhum arquivo enviado."}), 400

    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        buf = f.read()
        if ext == ".zip":
            try:
                with ZipFile(io.BytesIO(buf)) as z:
                    for info in z.infolist():
                        if info.is_dir():
                            continue
                        e = os.path.splitext(info.filename)[1].lower()
                        if e not in ('.ofx', '.txt'):
                            continue
                        zbuf = z.read(info.filename)
                        raw_files.append({"name": os.path.basename(info.filename), "ext": e, "buffer": zbuf, "size": len(zbuf)})
            except Exception as zip_err:
                return jsonify({"detail": f"Erro ao descompactar ZIP: {zip_err}"}), 400
        else:
            raw_files.append({"name": f.filename, "ext": ext, "buffer": buf, "size": len(buf)})

    if not raw_files:
        return jsonify({"detail": "Nenhum arquivo válido encontrado."}), 400

    em_session_cache[session_id] = {"files": raw_files, "analyzed": False, "createdAt": datetime.now()}
    return jsonify({
        "sessionId": session_id,
        "fileCount": len(raw_files),
        "ofxCount": sum(1 for r in raw_files if r["ext"] == ".ofx"),
        "txtCount": sum(1 for r in raw_files if r["ext"] == ".txt"),
        "files": [{"name": r["name"], "ext": r["ext"], "size": r["size"]} for r in raw_files]
    })


# ════════════════════════════════════════════════════════════════
# LOCAL FOLDERS / ZIPS
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/local-folders", methods=["GET"])
@require_login
def em_local_folders():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    folders_info = []
    for item in os.listdir(UPLOAD_DIR):
        item_path = os.path.join(UPLOAD_DIR, item)
        if not os.path.isdir(item_path):
            continue
        ofx_count = txt_count = total_size = 0
        for file in os.listdir(item_path):
            ext = os.path.splitext(file)[1].lower()
            if ext in ('.ofx', '.txt'):
                if ext == ".ofx": ofx_count += 1
                else: txt_count += 1
                total_size += os.path.getsize(os.path.join(item_path, file))
        if ofx_count + txt_count > 0:
            folders_info.append({"name": item, "fileCount": ofx_count + txt_count, "ofxCount": ofx_count, "txtCount": txt_count, "size": total_size})

    def get_key(x):
        return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x["name"])]
    folders_info.sort(key=get_key)
    return jsonify(folders_info)


@bp.route("/api/extratos/load-local-folder", methods=["POST"])
@require_login
def em_load_local_folder():
    body = request.get_json(force=True) or {}
    folder_name = body.get("folderName", "")
    if not folder_name:
        return jsonify({"detail": "folderName é obrigatório."}), 400
    folder_path = os.path.join(UPLOAD_DIR, folder_name)
    if not os.path.exists(folder_path):
        return jsonify({"detail": "Pasta da conta não encontrada."}), 404
    session_id = str(uuid.uuid4())
    raw_files = []
    for file in os.listdir(folder_path):
        ext = os.path.splitext(file)[1].lower()
        if ext not in ('.ofx', '.txt'):
            continue
        with open(os.path.join(folder_path, file), "rb") as f:
            buf = f.read()
        raw_files.append({"name": file, "ext": ext, "buffer": buf, "size": len(buf)})
    if not raw_files:
        return jsonify({"detail": "Nenhum arquivo válido encontrado na pasta."}), 400
    em_session_cache[session_id] = {"files": raw_files, "analyzed": False, "createdAt": datetime.now()}
    return jsonify({"sessionId": session_id, "fileCount": len(raw_files),
                    "ofxCount": sum(1 for r in raw_files if r["ext"] == ".ofx"),
                    "txtCount": sum(1 for r in raw_files if r["ext"] == ".txt"),
                    "files": [{"name": r["name"], "ext": r["ext"], "size": r["size"]} for r in raw_files]})


@bp.route("/api/extratos/local-zips", methods=["GET"])
@require_login
def em_local_zips():
    root_path = os.path.join(UPLOAD_DIR + "_zip")
    os.makedirs(root_path, exist_ok=True)
    zips_info = []
    for file in os.listdir(root_path):
        if not file.lower().endswith(".zip"):
            continue
        file_path = os.path.join(root_path, file)
        stats = os.stat(file_path)
        account_num = "Desconhecido"
        ofx_count = txt_count = 0
        try:
            with ZipFile(file_path, "r") as z:
                for info in z.infolist():
                    if info.is_dir(): continue
                    ext = os.path.splitext(info.filename)[1].lower()
                    if ext == ".ofx":
                        ofx_count += 1
                        if account_num == "Desconhecido":
                            content = z.read(info.filename).decode("utf-8", errors="ignore")
                            m = re.search(r"<ACCTID>([^<\r\n]+)", content, re.IGNORECASE)
                            if m: account_num = m.group(1).strip().replace(" ", "")
                    elif ext == ".txt":
                        txt_count += 1
        except Exception: pass
        zips_info.append({"name": file, "size": stats.st_size,
                          "mtime": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                          "account": account_num, "fileCount": ofx_count + txt_count,
                          "ofxCount": ofx_count, "txtCount": txt_count})
    return jsonify(zips_info)


@bp.route("/api/extratos/load-local-zip", methods=["POST"])
@require_login
def em_load_local_zip():
    body = request.get_json(force=True) or {}
    filename = body.get("filename", "")
    if not filename:
        return jsonify({"detail": "filename é obrigatório."}), 400
    file_path = os.path.join(UPLOAD_DIR + "_zip", filename)
    if not os.path.exists(file_path):
        return jsonify({"detail": "Arquivo ZIP não encontrado."}), 404
    session_id = str(uuid.uuid4())
    raw_files = []
    try:
        with ZipFile(file_path, "r") as z:
            for info in z.infolist():
                if info.is_dir(): continue
                ext = os.path.splitext(info.filename)[1].lower()
                if ext not in ('.ofx', '.txt'): continue
                buf = z.read(info.filename)
                raw_files.append({"name": os.path.basename(info.filename), "ext": ext, "buffer": buf, "size": len(buf)})
    except Exception as e:
        return jsonify({"detail": str(e)}), 500
    if not raw_files:
        return jsonify({"detail": "Nenhum arquivo válido no ZIP."}), 400
    em_session_cache[session_id] = {"files": raw_files, "analyzed": False, "createdAt": datetime.now()}
    return jsonify({"sessionId": session_id, "fileCount": len(raw_files),
                    "ofxCount": sum(1 for r in raw_files if r["ext"] == ".ofx"),
                    "txtCount": sum(1 for r in raw_files if r["ext"] == ".txt"),
                    "files": [{"name": r["name"], "ext": r["ext"], "size": r["size"]} for r in raw_files]})


# ════════════════════════════════════════════════════════════════
# ANALYZE
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/analyze/<session_id>", methods=["POST"])
@require_login
def em_analyze(session_id):
    body = request.get_json(force=True) or {}
    account_id = body.get("accountId")
    session = em_session_cache.get(session_id)
    if not session:
        return jsonify({"detail": "Sessão não encontrada."}), 404

    try:
        files_by_account = {}
        for f in session["files"]:
            file_acc = "generic"
            if f["ext"] == ".ofx":
                parsed = parse_ofx(f["buffer"], f["name"])
                if parsed.get("account"):
                    file_acc = parsed["account"].replace(" ", "")
            elif f["ext"] == ".txt":
                parsed_txt = parse_txt(f["buffer"], f["name"])
                if parsed_txt and parsed_txt.get("account"):
                    file_acc = parsed_txt["account"].replace(" ", "")
                else:
                    m = re.search(r"(\d{4,9}-\d|\d{5,10})", f["name"])
                    if m: file_acc = m.group(0).replace(" ", "")
            files_by_account.setdefault(file_acc, []).append(f)

        results = []
        all_account_results = []

        for acc_number, acc_files in files_by_account.items():
            transactions, investments, ofx_meta = [], [], []
            for f in acc_files:
                if f["ext"] == ".ofx":
                    parsed = parse_ofx(f["buffer"], f["name"])
                    transactions.extend(parsed["transactions"])
                    ofx_meta.append(build_ofx_meta(parsed))
                elif f["ext"] == ".txt":
                    r = parse_txt(f["buffer"], f["name"])
                    if r: investments.append(r)

            transactions.sort(key=get_tx_date)
            investments.sort(key=lambda x: x.get("periodSort") or "")

            account = None
            conn = get_em_db_connection()
            try:
                if account_id and len(files_by_account) == 1 and acc_number == "generic":
                    account = conn.execute("SELECT * FROM em_accounts WHERE id=?", (account_id,)).fetchone()
                if not account and acc_number != "generic":
                    account = conn.execute("SELECT * FROM em_accounts WHERE number=? AND bank=?", (acc_number, 'Banco do Brasil')).fetchone()
                    if not account:
                        new_id = str(uuid.uuid4())
                        conn.execute("INSERT INTO em_accounts (id,name,agency,number,bank,notes) VALUES (?,?,?,?,?,?)",
                                     (new_id, f"Conta {acc_number}", "", acc_number, "Banco do Brasil", ""))
                        conn.commit()
                        account = {"id": new_id, "name": f"Conta {acc_number}", "agency": "", "number": acc_number, "bank": "Banco do Brasil", "notes": ""}
                    else:
                        account = dict(account)
                elif account:
                    account = dict(account)
            finally:
                conn.close()

            custom_config = None
            if account:
                conn = get_em_db_connection()
                try:
                    overrides = conn.execute("SELECT config_key, config_value FROM em_detector_config WHERE account_id=?", (account["id"],)).fetchall()
                    if overrides:
                        import copy
                        custom_config = copy.copy(DETECTOR_CONFIG)
                        for ov in overrides:
                            custom_config[ov["config_key"]] = ov["config_value"]
                finally:
                    conn.close()

            analysis_res = run_analysis(transactions, investments, custom_config, ofx_meta)
            alerts, all_alerts, stats = analysis_res["alerts"], analysis_res["allAlerts"], analysis_res["stats"]

            if account:
                conn = get_em_db_connection()
                try:
                    resolved = conn.execute("SELECT title,description,resolution_note,resolved_by FROM em_alerts WHERE account_id=? AND resolved=1", (account["id"],)).fetchall()
                    for a in alerts:
                        for hist in resolved:
                            if hist["title"] == a.get("title") and hist["description"] == a.get("description"):
                                a["resolved"] = True
                                a["resolutionNote"] = hist["resolution_note"]
                                a["resolvedBy"] = hist["resolved_by"]
                                a["resolvedAt"] = datetime.now(tz=timezone.utc).isoformat()
                except Exception: pass
                finally:
                    conn.close()

            sub_id = session_id if len(files_by_account) == 1 else str(uuid.uuid4())
            all_account_results.append({"account": account, "transactions": transactions,
                                        "investments": investments, "alerts": alerts,
                                        "allAlerts": all_alerts, "stats": stats,
                                        "currentSubSessionId": sub_id, "accFiles": acc_files})

        if len(all_account_results) > 1:
            run_cross_account_analysis(all_account_results)

        for res in all_account_results:
            acc, txs, invs, alrts, all_alrts, stts, sub_id, afs = (
                res["account"], res["transactions"], res["investments"], res["alerts"],
                res["allAlerts"], res["stats"], res["currentSubSessionId"], res["accFiles"]
            )
            db_session, db_alerts, db_txns = _build_db_records(sub_id, acc, txs, invs, all_alrts, stts, afs)
            try:
                save_em_session(db_session, db_alerts, db_txns)
            except Exception as db_err:
                print("Sessão já persistida ou erro:", db_err)

            em_session_cache[sub_id] = {
                "files": afs,
                "transactions": [{**t, "date": t["date"].isoformat() if isinstance(t["date"], datetime) else t["date"]} for t in txs],
                "investments": invs, "alerts": all_alrts, "stats": stts,
                "account": acc, "analyzed": True, "createdAt": datetime.now()
            }
            results.append({"sessionId": sub_id, "account": acc, "summary": {
                "transactions": len(txs), "investments": len(invs),
                "alerts": len(alrts), "critical": stts.get("criticalAlerts", 0),
                "warning": stts.get("warningAlerts", 0), "info": stts.get("infoAlerts", 0),
                "flagged": stts.get("flaggedCount", 0)
            }})

        return jsonify({"success": True, "accountsAnalyzed": results})
    except Exception as err:
        print("Erro em analyze:", err)
        return jsonify({"detail": str(err)}), 500


@bp.route("/api/extratos/analyze-batch", methods=["POST"])
@require_login
def em_analyze_batch():
    if not os.path.exists(UPLOAD_DIR):
        return jsonify({"success": False, "error": "Pasta de uploads não encontrada."}), 400
    results = []
    accounts_by_num = {}
    conn = get_em_db_connection()
    try:
        for a in conn.execute("SELECT * FROM em_accounts").fetchall():
            key = f"{normalize_acc_number(a['number'])}|{a['bank']}"
            accounts_by_num[key] = dict(a)
    finally:
        conn.close()

    global_processed = global_alerts = global_critical = global_warning = 0

    for folder_name in os.listdir(UPLOAD_DIR):
        folder_path = os.path.join(UPLOAD_DIR, folder_name)
        if not os.path.isdir(folder_path): continue
        acc_files = []
        for file in os.listdir(folder_path):
            ext = os.path.splitext(file)[1].lower()
            if ext not in ('.ofx', '.txt'): continue
            with open(os.path.join(folder_path, file), "rb") as fh:
                buf = fh.read()
            acc_files.append({"name": file, "ext": ext, "buffer": buf})
        if not acc_files: continue

        transactions, investments, ofx_meta = [], [], []
        for f in acc_files:
            if f["ext"] == ".ofx":
                try:
                    parsed = parse_ofx(f["buffer"], f["name"])
                    transactions.extend(parsed["transactions"])
                    ofx_meta.append(build_ofx_meta(parsed))
                except Exception as pe: print(f"Erro parseOFX: {pe}")
            elif f["ext"] == ".txt":
                try:
                    r = parse_txt(f["buffer"], f["name"])
                    if r: investments.append(r)
                except Exception as pe: print(f"Erro parseTXT: {pe}")

        transactions.sort(key=get_tx_date)
        investments.sort(key=lambda x: x.get("periodSort") or "")

        acc_number = folder_name.replace(" ", "")
        conn = get_em_db_connection()
        account = None
        try:
            account = conn.execute("SELECT * FROM em_accounts WHERE number=? AND bank=?", (acc_number, 'Banco do Brasil')).fetchone()
            if not account:
                norm_key = f"{normalize_acc_number(acc_number)}|Banco do Brasil"
                if norm_key in accounts_by_num:
                    account = accounts_by_num[norm_key]
                else:
                    new_id = str(uuid.uuid4())
                    conn.execute("INSERT INTO em_accounts (id,name,agency,number,bank,notes) VALUES (?,?,?,?,?,?)",
                                 (new_id, f"Conta {folder_name}", "", acc_number, "Banco do Brasil", "Criada via análise em lote"))
                    conn.commit()
                    account = {"id": new_id, "name": f"Conta {folder_name}", "number": acc_number, "bank": "Banco do Brasil"}
                    accounts_by_num[norm_key] = account
            else:
                account = dict(account)
        finally:
            conn.close()

        analysis_res = run_analysis(transactions, investments, None, ofx_meta)
        stats = analysis_res["stats"]
        session_id = str(uuid.uuid4())
        db_session, db_alerts, db_txns = _build_db_records(session_id, account, transactions, investments, analysis_res["allAlerts"], stats, acc_files)
        save_em_session(db_session, db_alerts, db_txns)
        global_processed += 1
        global_alerts += len(analysis_res["alerts"])
        global_critical += stats.get("criticalAlerts", 0)
        global_warning += stats.get("warningAlerts", 0)
        results.append({"folderName": folder_name, "accountId": account["id"], "sessionId": session_id,
                        "txCount": len(transactions), "alertCount": len(analysis_res["alerts"]),
                        "criticalCount": stats.get("criticalAlerts", 0)})

    return jsonify({"success": True, "totalAnalyzed": global_processed, "totalAlerts": global_alerts,
                    "totalCritical": global_critical, "totalWarning": global_warning, "results": results})


# ════════════════════════════════════════════════════════════════
# SESSIONS
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/sessions/<session_id>", methods=["GET"])
@require_login
def em_get_session(session_id):
    data = get_em_session_data(session_id)
    if not data:
        return jsonify({"detail": "Sessão não encontrada."}), 404
    return jsonify({"sessionId": session_id, "transactions": data["transactions"],
                    "investments": data["investments"], "alerts": data["alerts"],
                    "stats": data["stats"], "account": data["account"]})


@bp.route("/api/extratos/sessions/<session_id>", methods=["DELETE"])
@require_login
def em_delete_session(session_id):
    em_session_cache.pop(session_id, None)
    conn = get_em_db_connection()
    try:
        conn.execute("DELETE FROM em_analysis_sessions WHERE id=?", (session_id,))
        conn.commit()
        return jsonify({"deleted": True})
    finally:
        conn.close()


@bp.route("/api/extratos/sessions/<session_id>/compare/<sid2>", methods=["GET"])
@require_login
def em_compare_sessions(session_id, sid2):
    s1 = get_em_session_data(session_id)
    s2 = get_em_session_data(sid2)
    if not s1 or not s2:
        return jsonify({"detail": "Uma ou ambas as sessões não encontradas."}), 404
    st1, st2 = s1.get("stats") or {}, s2.get("stats") or {}
    diff = {k: st2.get(k, 0) - st1.get(k, 0) for k in
            ("totalTransactions", "totalCredits", "totalDebits", "totalAlerts", "criticalAlerts", "lastBalance", "totalRendimento", "riskScore")}
    s1_keys = {a["title"] + "|" + a["description"] for a in s1.get("alerts", [])}
    new_alerts = [a for a in s2.get("alerts", []) if (a["title"] + "|" + a["description"]) not in s1_keys][:10]
    return jsonify({"success": True, "diff": diff, "newAlerts": new_alerts, "stats1": st1, "stats2": st2})


@bp.route("/api/extratos/latest-session", methods=["GET"])
@require_login
def em_latest_session():
    account_id = request.args.get("accountId")
    conn = get_em_db_connection()
    try:
        row = conn.execute("""
            SELECT s.*,a.id AS acc_id,a.name AS acc_name,a.agency AS acc_agency,a.number AS acc_number,a.bank AS acc_bank,a.notes AS acc_notes
            FROM em_analysis_sessions s LEFT JOIN em_accounts a ON a.id=s.account_id
            WHERE (? IS NULL OR s.account_id=?) ORDER BY s.analyzed_at DESC LIMIT 1
        """, (account_id, account_id)).fetchone()
        if not row:
            return jsonify({"detail": "Nenhuma sessão encontrada."}), 404
        return jsonify({
            "session": {k: row[k] for k in ("id","account_id","analyzed_at","period_start","period_end","file_count","tx_count","invest_count","alert_count","critical_count","warning_count")},
            "account": {"id": row["acc_id"], "name": row["acc_name"], "agency": row["acc_agency"], "number": row["acc_number"], "bank": row["acc_bank"], "notes": row["acc_notes"]} if row["acc_id"] else None
        })
    finally:
        conn.close()


@bp.route("/api/extratos/stats/global", methods=["GET"])
@require_login
def em_stats_global():
    conn = get_em_db_connection()
    try:
        accounts     = conn.execute("SELECT COUNT(*) FROM em_accounts").fetchone()[0]
        sessions     = conn.execute("SELECT COUNT(*) FROM em_analysis_sessions").fetchone()[0]
        total_alerts = conn.execute("SELECT COUNT(*) FROM em_alerts").fetchone()[0]
        critical     = conn.execute("SELECT COUNT(*) FROM em_alerts WHERE severity='critical' AND resolved=0").fetchone()[0]
        warning      = conn.execute("SELECT COUNT(*) FROM em_alerts WHERE severity='warning' AND resolved=0").fetchone()[0]
        resolved     = conn.execute("SELECT COUNT(*) FROM em_alerts WHERE resolved=1").fetchone()[0]
        total_txns   = conn.execute("SELECT COUNT(*) FROM em_transactions_log").fetchone()[0]
        total_credits = conn.execute("SELECT COALESCE(SUM(amount),0) FROM em_transactions_log WHERE amount>0").fetchone()[0]
        total_debits  = conn.execute("SELECT COALESCE(SUM(ABS(amount)),0) FROM em_transactions_log WHERE amount<0").fetchone()[0]
        top_risk = conn.execute("""
            SELECT a.id,a.name,a.number,
              COUNT(CASE WHEN al.severity='critical' AND al.resolved=0 THEN 1 END) as critical,
              COUNT(CASE WHEN al.severity='warning'  AND al.resolved=0 THEN 1 END) as warning
            FROM em_accounts a LEFT JOIN em_alerts al ON al.account_id=a.id
            GROUP BY a.id ORDER BY critical DESC,warning DESC LIMIT 5
        """).fetchall()
        return jsonify({"accounts": accounts, "sessions": sessions, "totalAlerts": total_alerts,
                        "criticalAlerts": critical, "warningAlerts": warning, "resolvedAlerts": resolved,
                        "totalTxns": total_txns, "totalCredits": total_credits, "totalDebits": total_debits,
                        "topRiskAccounts": [dict(r) for r in top_risk],
                        "timestamp": datetime.now(tz=timezone.utc).isoformat()})
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# ALERTS
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/alerts/summary", methods=["GET"])
@require_login
def em_alerts_summary():
    conn = get_em_db_connection()
    try:
        rows = conn.execute("""
            SELECT a.id as account_id,a.name,a.number,
              COUNT(al.id) as total,
              COUNT(CASE WHEN al.severity='critical' AND al.resolved=0 THEN 1 END) as critical,
              COUNT(CASE WHEN al.severity='warning'  AND al.resolved=0 THEN 1 END) as warning,
              COUNT(CASE WHEN al.resolved=0 THEN 1 END) as unresolved
            FROM em_accounts a LEFT JOIN em_alerts al ON al.account_id=a.id
            GROUP BY a.id ORDER BY critical DESC,warning DESC
        """).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@bp.route("/api/extratos/alerts/<alert_id>/resolve", methods=["PATCH"])
@require_login
def em_resolve_alert(alert_id):
    body = request.get_json(force=True) or {}
    note = body.get("note", "")
    resolved_by = body.get("resolvedBy", "Sistema")
    conn = get_em_db_connection()
    try:
        if not conn.execute("SELECT id FROM em_alerts WHERE id=?", (alert_id,)).fetchone():
            return jsonify({"detail": "Alerta não encontrado."}), 404
        conn.execute("UPDATE em_alerts SET resolved=1,resolved_at=?,resolved_by=?,resolution_note=? WHERE id=?",
                     (datetime.now(tz=timezone.utc).isoformat(), resolved_by, note, alert_id))
        conn.commit()
        return jsonify({"success": True, "alertId": alert_id})
    finally:
        conn.close()


@bp.route("/api/extratos/alerts/<alert_id>/unresolve", methods=["PATCH"])
@require_login
def em_unresolve_alert(alert_id):
    conn = get_em_db_connection()
    try:
        if not conn.execute("SELECT id FROM em_alerts WHERE id=?", (alert_id,)).fetchone():
            return jsonify({"detail": "Alerta não encontrado."}), 404
        conn.execute("UPDATE em_alerts SET resolved=0,resolved_at=NULL,resolved_by=NULL,resolution_note=NULL WHERE id=?", (alert_id,))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


@bp.route("/api/extratos/alerts/<alert_id>/note", methods=["PATCH"])
@require_login
def em_update_alert_note(alert_id):
    body = request.get_json(force=True) or {}
    note = str(body.get("note", "")).strip()
    if not note:
        return jsonify({"detail": "A nota não pode estar vazia."}), 400
    conn = get_em_db_connection()
    try:
        if not conn.execute("SELECT id FROM em_alerts WHERE id=?", (alert_id,)).fetchone():
            return jsonify({"detail": "Alerta não encontrado."}), 404
        conn.execute("UPDATE em_alerts SET resolution_note=? WHERE id=?", (note, alert_id))
        conn.commit()
        return jsonify({"success": True, "alertId": alert_id, "note": note})
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# ATTACHMENTS
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/alerts/<alert_id>/attachments", methods=["POST"])
@require_login
def em_add_attachment(alert_id):
    conn = get_em_db_connection()
    try:
        if not conn.execute("SELECT id FROM em_alerts WHERE id=?", (alert_id,)).fetchone():
            return jsonify({"detail": "Alerta não encontrado."}), 404
        file = request.files.get("file")
        if not file:
            return jsonify({"detail": "Arquivo não enviado."}), 400
        note = request.form.get("note", "")
        os.makedirs(ATT_DIR, exist_ok=True)
        stored_name = f"{uuid.uuid4()}{os.path.splitext(secure_filename(file.filename))[1]}"
        dest = os.path.join(ATT_DIR, stored_name)
        file.save(dest)
        att_id = str(uuid.uuid4())
        size = os.path.getsize(dest)
        conn.execute("INSERT INTO em_alert_attachments (id,alert_id,filename,mimetype,size,stored_name,note) VALUES (?,?,?,?,?,?,?)",
                     (att_id, alert_id, file.filename, file.content_type, size, stored_name, note))
        conn.commit()
        return jsonify({"success": True, "id": att_id, "filename": file.filename, "size": size})
    finally:
        conn.close()


@bp.route("/api/extratos/alerts/<alert_id>/attachments", methods=["GET"])
@require_login
def em_get_attachments(alert_id):
    conn = get_em_db_connection()
    try:
        rows = conn.execute("SELECT id,filename,mimetype,size,note,uploaded_at FROM em_alert_attachments WHERE alert_id=?", (alert_id,)).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@bp.route("/api/extratos/attachments/<att_id>", methods=["GET"])
@require_login
def em_download_attachment(att_id):
    conn = get_em_db_connection()
    try:
        att = conn.execute("SELECT * FROM em_alert_attachments WHERE id=?", (att_id,)).fetchone()
        if not att:
            return jsonify({"detail": "Anexo não encontrado."}), 404
        file_path = os.path.join(ATT_DIR, att["stored_name"])
        if not os.path.exists(file_path):
            return jsonify({"detail": "Arquivo físico não encontrado."}), 404
        return send_file(file_path, mimetype=att["mimetype"], as_attachment=True, download_name=att["filename"])
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# EXPORT
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/export/excel/<session_id>", methods=["GET"])
@require_login
def em_export_excel(session_id):
    s = get_em_session_data(session_id)
    if not s:
        return jsonify({"detail": "Sessão não encontrada."}), 404
    try:
        transactions = []
        for t in s["transactions"]:
            dt_obj = datetime.now()
            try: dt_obj = datetime.fromisoformat(t["date"])
            except Exception: pass
            transactions.append({**t, "date": dt_obj})
        buf = build_excel(transactions, s["investments"], s["alerts"], s["stats"])
        return send_file(io.BytesIO(buf),
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=f"ExpertMoney_{date_tag()}.xlsx")
    except Exception as e:
        return jsonify({"detail": str(e)}), 500


@bp.route("/api/extratos/export/pdf/<session_id>", methods=["GET"])
@require_login
def em_export_pdf(session_id):
    s = get_em_session_data(session_id)
    if not s:
        return jsonify({"detail": "Sessão não encontrada."}), 404
    try:
        transactions = []
        for t in s["transactions"]:
            dt_obj = datetime.now()
            try: dt_obj = datetime.fromisoformat(t["date"])
            except Exception: pass
            transactions.append({**t, "date": dt_obj})
        buf = build_pdf(transactions, s["investments"], s["alerts"], s["stats"], s["account"])
        return send_file(io.BytesIO(buf), mimetype="application/pdf",
                         as_attachment=True, download_name=f"ExpertMoney_{date_tag()}.pdf")
    except Exception as e:
        return jsonify({"detail": str(e)}), 500


@bp.route("/api/extratos/export/csv/<session_id>", methods=["GET"])
@require_login
def em_export_csv(session_id):
    s = get_em_session_data(session_id)
    if not s:
        return jsonify({"detail": "Sessão não encontrada."}), 404
    try:
        csv_str = generate_csv_transactions(s["transactions"])
        bom_csv = "﻿" + csv_str
        return Response(bom_csv, mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename=ExpertMoney_{date_tag()}.csv"})
    except Exception as e:
        return jsonify({"detail": str(e)}), 500


# ════════════════════════════════════════════════════════════════
# SEARCH / CDI / AUDIT / CONFIG
# ════════════════════════════════════════════════════════════════
@bp.route("/api/extratos/search", methods=["GET", "POST"])
@require_login
def em_search():
    if request.method == "POST":
        body = request.get_json(force=True) or {}
    else:
        body = dict(request.args)
    for k in ("amount", "amountTolerance", "amountMin", "amountMax", "limit"):
        if body.get(k) is not None and body[k] != "":
            try: body[k] = float(body[k])
            except ValueError: pass
    if body.get("flagged") is not None:
        body["flagged"] = body["flagged"] is True or body["flagged"] == "true"
    return jsonify(search_transactions(body))


@bp.route("/api/extratos/cdi", methods=["GET"])
@require_login
def em_cdi():
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados/ultimos/12?formato=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
        return jsonify([{"date": d["data"], "value": float(d["valor"])} for d in parsed])
    except Exception as e:
        return jsonify({"detail": f"Erro ao buscar CDI do BACEN: {e}"}), 502


@bp.route("/api/extratos/audit/<account_id>", methods=["GET"])
@require_login
def em_audit(account_id):
    conn = get_em_db_connection()
    try:
        sessions = conn.execute("""
            SELECT id,analyzed_at,tx_count,alert_count,critical_count,warning_count,period_start,period_end
            FROM em_analysis_sessions WHERE account_id=? ORDER BY analyzed_at DESC
        """, (account_id,)).fetchall()
        resolved = conn.execute("""
            SELECT id,title,severity,category,resolved_at,resolved_by,resolution_note
            FROM em_alerts WHERE account_id=? AND resolved=1 ORDER BY resolved_at DESC
        """, (account_id,)).fetchall()
        events = []
        for s in sessions:
            events.append({"type": "analysis", "timestamp": s["analyzed_at"], "sessionId": s["id"],
                           "description": f"Análise: {s['tx_count']} transações, {s['alert_count']} alertas ({s['critical_count']} críticos)",
                           "meta": {"tx_count": s["tx_count"], "alert_count": s["alert_count"]}})
        for a in resolved:
            if a["resolved_at"]:
                events.append({"type": "resolve", "timestamp": a["resolved_at"], "alertId": a["id"],
                               "severity": a["severity"],
                               "description": f"Alerta resolvido: \"{(a['title'] or '').split('|')[0][:60]}\" por {a['resolved_by'] or 'Sistema'}",
                               "meta": {"category": a["category"], "note": a["resolution_note"]}})
        events.sort(key=lambda x: x["timestamp"] or "", reverse=True)
        return jsonify({"events": events, "accountId": account_id})
    finally:
        conn.close()


@bp.route("/api/extratos/accounts/<account_id>/config", methods=["GET"])
@require_login
def em_get_account_config(account_id):
    conn = get_em_db_connection()
    try:
        account = conn.execute("SELECT * FROM em_accounts WHERE id=?", (account_id,)).fetchone()
        if not account:
            return jsonify({"detail": "Conta não encontrada."}), 404
        overrides = {r["config_key"]: r["config_value"] for r in conn.execute("SELECT config_key,config_value FROM em_detector_config WHERE account_id=?", (account_id,)).fetchall()}
        globals_cfg = {r["config_key"]: r["config_value"] for r in conn.execute("SELECT config_key,config_value FROM em_detector_config WHERE account_id IS NULL").fetchall()}
        entries = []
        for key, default_val in DETECTOR_CONFIG.items():
            if not isinstance(default_val, (int, float)): continue
            entries.append({"key": key, "default": default_val, "global": globals_cfg.get(key),
                            "override": overrides.get(key),
                            "effective": overrides.get(key) if overrides.get(key) is not None else globals_cfg.get(key) if globals_cfg.get(key) is not None else default_val})
        return jsonify({"accountId": account_id, "accountName": account["name"], "entries": entries})
    finally:
        conn.close()


@bp.route("/api/extratos/accounts/<account_id>/config", methods=["PUT"])
@require_login
def em_put_account_config(account_id):
    body = request.get_json(force=True) or {}
    key = body.get("key", "")
    value = body.get("value")
    if key not in DETECTOR_CONFIG:
        return jsonify({"detail": f"Chave '{key}' não é válida."}), 400
    try: num_val = float(value)
    except (TypeError, ValueError):
        return jsonify({"detail": "Valor deve ser numérico."}), 400
    conn = get_em_db_connection()
    try:
        if not conn.execute("SELECT id FROM em_accounts WHERE id=?", (account_id,)).fetchone():
            return jsonify({"detail": "Conta não encontrada."}), 404
        conn.execute("""
            INSERT INTO em_detector_config (account_id,config_key,config_value,updated_at)
            VALUES (?,?,?,datetime('now','localtime'))
            ON CONFLICT(account_id,config_key) DO UPDATE SET config_value=excluded.config_value,updated_at=excluded.updated_at
        """, (account_id, key, num_val))
        conn.commit()
        return jsonify({"success": True, "accountId": account_id, "key": key, "value": num_val})
    finally:
        conn.close()


@bp.route("/api/extratos/accounts/<account_id>/config/<key>", methods=["DELETE"])
@require_login
def em_delete_account_config(account_id, key):
    conn = get_em_db_connection()
    try:
        cur = conn.execute("DELETE FROM em_detector_config WHERE account_id=? AND config_key=?", (account_id, key))
        conn.commit()
        return jsonify({"success": True, "removed": cur.rowcount > 0})
    finally:
        conn.close()


@bp.route("/api/extratos/sessions/<session_id>/email-summary", methods=["GET"])
@require_login
def em_email_summary(session_id):
    s = get_em_session_data(session_id)
    if not s:
        return jsonify({"detail": "Sessão não encontrada."}), 404
    stats = s.get("stats") or {}
    alerts = s.get("alerts") or []
    account = s.get("account")
    criticals = [a for a in alerts if a.get("severity") == "critical" and not a.get("resolved")]
    warnings  = [a for a in alerts if a.get("severity") == "warning"  and not a.get("resolved")]
    subject = f"ExpertMoney — Análise {account['name'] if account else ''}: {len(criticals)} alerta(s) crítico(s)"
    lines = [
        "ExpertMoney Analyzer — Relatório de Análise Financeira",
        f"Conta: {account['name']} ({account.get('number')})" if account else "",
        f"Score de Risco: {stats.get('riskScore', 0)}/100",
        f"Alertas Críticos: {len(criticals)} | Atenção: {len(warnings)}",
    ]
    return jsonify({"subject": subject, "text": "\n".join(l for l in lines if l), "account": account,
                    "stats": {"criticalAlerts": len(criticals), "warningAlerts": len(warnings), "riskScore": stats.get("riskScore", 0)}})


@bp.route("/api/extratos/cross-analysis", methods=["GET"])
@require_login
def em_cross_analysis():
    account_id = request.args.get("accountId")
    conn = get_em_db_connection()
    try:
        rows = conn.execute("""
            SELECT t.*,a.number as acc_number,a.name as acc_name
            FROM em_transactions_log t JOIN em_accounts a ON t.account_id=a.id
            WHERE t.session_id IN (
              SELECT s.id FROM (
                SELECT id,account_id,ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY analyzed_at DESC) as rn
                FROM em_analysis_sessions
              ) s WHERE s.rn=1
            ) ORDER BY t.date ASC
        """).fetchall()
        txns = []
        for r in rows:
            flags = []
            try:
                if r["flags_json"]: flags = json.loads(r["flags_json"])
            except Exception: pass
            try:
                dt = datetime.fromisoformat(str(r["date"]).replace("Z", "+00:00"))
            except Exception:
                dt = datetime.min.replace(tzinfo=timezone.utc)
            txns.append({"id": r["id"], "accountId": r["account_id"], "accNumber": r["acc_number"],
                         "accName": r["acc_name"], "type": r["type"], "date": dt,
                         "dateStr": r["date_str"], "amount": r["amount"], "memo": r["memo"] or "",
                         "period": r["period"], "flagged": r["flagged"] == 1, "flags": flags})

        account_numbers = list({t["accNumber"] for t in txns})
        debits  = [t for t in txns if t["amount"] < 0]
        credits = [t for t in txns if t["amount"] > 0]
        matched_d, matched_c = set(), set()
        reconciled = []

        def get_kws(memo):
            return [w for w in re.split(r"[\s\-\/,.:]+", (memo or "").upper()) if len(w) > 3 and not re.match(r"^\d+$", w)]

        def is_similar(m1, m2):
            w1, w2 = get_kws(m1), get_kws(m2)
            if not w1 or not w2: return False
            common = [w for w in w1 if any(w in x or x in w for x in w2)]
            return len(common) >= 2 or (len(w1) == 1 and len(w2) == 1 and w1[0] == w2[0])

        candidates = []
        for d in debits:
            for c in credits:
                if c["accountId"] == d["accountId"]: continue
                if abs(abs(d["amount"]) - c["amount"]) >= 0.05: continue
                gap = (c["date"] - d["date"]).total_seconds() / 86400.0
                if gap < 0 or gap > 2: continue
                candidates.append({"d": d, "c": c, "score": (1 - gap / 2) * 0.5 + (1.0 if is_similar(d["memo"], c["memo"]) else 0.0) * 0.5})
        candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in candidates:
            d, c = cand["d"], cand["c"]
            if d["id"] in matched_d or c["id"] in matched_c: continue
            matched_d.add(d["id"]); matched_c.add(c["id"])
            reconciled.append({"id": f"rec-{d['id']}-{c['id']}", "amount": c["amount"], "dateStr": d["dateStr"],
                               "origin": {"accountId": d["accountId"], "number": d["accNumber"], "memo": d["memo"]},
                               "dest":   {"accountId": c["accountId"], "number": c["accNumber"], "memo": c["memo"]}})

        if account_id:
            reconciled = [r for r in reconciled if r["origin"]["accountId"] == account_id or r["dest"]["accountId"] == account_id]

        return jsonify({"success": True, "summary": {"accountsCount": len(account_numbers),
                        "reconciledCount": len(reconciled)}, "reconciled": reconciled,
                        "discrepancies": [], "duplicates": [], "smurfing": []})
    finally:
        conn.close()
