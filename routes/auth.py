"""Blueprint: Autenticacao multi-usuario com niveis de acesso"""

import hashlib
import os
from flask import Blueprint, request, jsonify, session
from routes._shared import get_db
from routes.helpers import rate_limited

bp = Blueprint("auth", __name__)


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def init_usuarios_table(app):
    conn = app._get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT DEFAULT '',
        login TEXT NOT NULL UNIQUE,
        senha_hash TEXT NOT NULL,
        nivel TEXT NOT NULL DEFAULT 'operador'
            CHECK (nivel IN ('admin','operador','leitor')),
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT DEFAULT (datetime('now','localtime')),
        atualizado_em TEXT DEFAULT (datetime('now','localtime'))
    )""")
    conn.commit()


def _seed_admin(admin_password, app):
    if not admin_password:
        return
    conn = app._get_db()
    row = conn.execute("SELECT id FROM usuarios WHERE login='admin' AND ativo=1").fetchone()
    if row:
        return
    conn.execute(
        "INSERT INTO usuarios (nome,email,login,senha_hash,nivel,ativo) VALUES (?,?,?,?,?,1)",
        ("Administrador", "admin@inaja.pr.gov.br", "admin", _hash(admin_password), "admin"),
    )
    conn.commit()


def init_auth_system(admin_password: str, app):
    init_usuarios_table(app)
    _seed_admin(admin_password, app)


def init_auth_hash(admin_password: str):
    pass  # compat


def _usuario_to_dict(row) -> dict:
    d = {
        "id": row["id"],
        "nome": row["nome"],
        "email": row["email"],
        "login": row["login"],
        "nivel": row["nivel"],
        "ativo": bool(row["ativo"]),
        "criado_em": row["criado_em"],
        "atualizado_em": row["atualizado_em"],
    }
    return d


# ── Login ─────────────────────────────────────────────

@bp.route("/api/auth/login", methods=["POST"])
def login():
    d = request.get_json(force=True) or {}
    login_input = (d.get("login") or "").strip().lower()
    senha = d.get("senha") or ""

    if not login_input or not senha:
        return jsonify({"ok": False, "error": "Informe login e senha"}), 400

    ip = request.remote_addr or "unknown"
    if rate_limited(f"login:{ip}", max_hits=10, window=60):
        return jsonify({"ok": False, "error": "Muitas tentativas. Aguarde 1 minuto."}), 429

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE login=? AND ativo=1", (login_input,)
    ).fetchone()

    if not row or row["senha_hash"] != _hash(senha):
        return jsonify({"ok": False, "error": "Login ou senha invalidos"}), 401

    session["usuario_id"] = row["id"]
    session["usuario_login"] = row["login"]
    session["usuario_nome"] = row["nome"]
    session["usuario_nivel"] = row["nivel"]
    session.permanent = False

    return jsonify({"ok": True, "usuario": _usuario_to_dict(row)})


# ── Verificar sessao ─────────────────────────────────

@bp.route("/api/auth/verificar", methods=["GET"])
def verificar_auth():
    if "usuario_id" not in session:
        return jsonify({"autenticado": False, "nome": None, "nivel": None})
    return jsonify({
        "autenticado": True,
        "nome": session.get("usuario_nome"),
        "nivel": session.get("usuario_nivel"),
        "login": session.get("usuario_login"),
    })


# ── Logout ────────────────────────────────────────────

@bp.route("/api/auth/sair", methods=["POST"])
def logout():
    for k in ("usuario_id", "usuario_login", "usuario_nome", "usuario_nivel"):
        session.pop(k, None)
    return jsonify({"ok": True})


# ── Compat: POST /api/auth/adm (senha direta ADM_PASSWORD) ─

@bp.route("/api/auth/adm", methods=["POST"])
def auth_adm_legacy():
    d = request.get_json(force=True) or {}
    senha = d.get("senha", "")
    admin_password = os.environ.get("ADM_PASSWORD", "").strip()
    if not admin_password:
        return jsonify({"ok": False, "error": "Senha administrativa nao configurada."}), 503
    if senha != admin_password:
        return jsonify({"ok": False, "error": "Senha incorreta"}), 401

    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE login='admin' AND ativo=1").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO usuarios (nome,email,login,senha_hash,nivel,ativo) VALUES (?,?,?,?,?,1)",
            ("Administrador", "admin@inaja.pr.gov.br", "admin", _hash(admin_password), "admin"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM usuarios WHERE login='admin' AND ativo=1").fetchone()

    session["usuario_id"] = row["id"]
    session["usuario_login"] = row["login"]
    session["usuario_nome"] = row["nome"]
    session["usuario_nivel"] = "admin"
    session.permanent = False
    return jsonify({"ok": True})


# ── CRUD de usuarios (admin only) ────────────────────

@bp.route("/api/auth/usuarios", methods=["GET"])
def listar_usuarios():
    if "usuario_id" not in session:
        return jsonify({"error": "Nao autorizado"}), 403
    rows = get_db().execute(
        "SELECT * FROM usuarios ORDER BY ativo DESC, nome ASC"
    ).fetchall()
    return jsonify([_usuario_to_dict(r) for r in rows])


@bp.route("/api/auth/usuarios", methods=["POST"])
def criar_usuario():
    if session.get("usuario_nivel") != "admin":
        return jsonify({"error": "Nao autorizado"}), 403
    d = request.get_json(force=True) or {}
    nome = (d.get("nome") or "").strip()
    email = (d.get("email") or "").strip()
    login = (d.get("login") or "").strip().lower()
    senha = d.get("senha") or ""
    nivel = (d.get("nivel") or "operador").strip().lower()

    errs = []
    if not nome: errs.append("Nome obrigatorio")
    if not login or len(login) < 3: errs.append("Login deve ter 3+ caracteres")
    if not senha or len(senha) < 4: errs.append("Senha deve ter 4+ caracteres")
    if nivel not in ("admin", "operador", "leitor"): errs.append("Nivel invalido")
    if errs:
        return jsonify({"ok": False, "error": ". ".join(errs)}), 400

    conn = get_db()
    if conn.execute("SELECT id FROM usuarios WHERE login=?", (login,)).fetchone():
        return jsonify({"ok": False, "error": f"Login '{login}' ja existe"}), 409

    conn.execute(
        "INSERT INTO usuarios (nome,email,login,senha_hash,nivel,ativo) VALUES (?,?,?,?,?,1)",
        (nome, email, login, _hash(senha), nivel),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM usuarios WHERE login=?", (login,)).fetchone()
    return jsonify({"ok": True, "usuario": _usuario_to_dict(row)}), 201


@bp.route("/api/auth/usuarios/<int:uid>", methods=["PUT"])
def atualizar_usuario(uid: int):
    if session.get("usuario_nivel") != "admin":
        return jsonify({"error": "Nao autorizado"}), 403
    d = request.get_json(force=True) or {}
    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    if not row:
        return jsonify({"error": "Usuario nao encontrado"}), 404

    nome = (d.get("nome") or row["nome"]).strip()
    email = d.get("email", row["email"] or "").strip()
    login = (d.get("login") or row["login"]).strip().lower()
    nivel = (d.get("nivel") or row["nivel"]).strip().lower()
    ativo = d.get("ativo", bool(row["ativo"]))

    if nivel not in ("admin", "operador", "leitor"):
        return jsonify({"error": "Nivel invalido"}), 400
    if conn.execute("SELECT id FROM usuarios WHERE login=? AND id!=?", (login, uid)).fetchone():
        return jsonify({"error": f"Login '{login}' ja existe"}), 409

    senha_hash = row["senha_hash"]
    if d.get("senha"):
        senha_hash = _hash(d["senha"])

    conn.execute(
        "UPDATE usuarios SET nome=?,email=?,login=?,senha_hash=?,nivel=?,ativo=?,atualizado_em=datetime('now','localtime') WHERE id=?",
        (nome, email, login, senha_hash, nivel, 1 if ativo else 0, uid),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    return jsonify({"ok": True, "usuario": _usuario_to_dict(row)})


@bp.route("/api/auth/usuarios/<int:uid>", methods=["DELETE"])
def deletar_usuario(uid: int):
    if session.get("usuario_nivel") != "admin":
        return jsonify({"error": "Nao autorizado"}), 403
    if session.get("usuario_id") == uid:
        return jsonify({"error": "Voce nao pode desativar a si mesmo"}), 400
    conn = get_db()
    conn.execute("UPDATE usuarios SET ativo=0, atualizado_em=datetime('now','localtime') WHERE id=?", (uid,))
    conn.commit()
    return jsonify({"ok": True})


# ── Alterar propria senha (qualquer usuario logado) ──

@bp.route("/api/auth/senha", methods=["PUT"])
def alterar_senha():
    if "usuario_id" not in session:
        return jsonify({"error": "Nao autenticado"}), 401
    d = request.get_json(force=True) or {}
    senha_atual = d.get("senha_atual", "")
    senha_nova = d.get("senha_nova", "")

    if not senha_atual or not senha_nova:
        return jsonify({"ok": False, "error": "Informe senha atual e nova senha"}), 400
    if len(senha_nova) < 4:
        return jsonify({"ok": False, "error": "Nova senha deve ter 4+ caracteres"}), 400

    conn = get_db()
    uid = session["usuario_id"]
    row = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    if not row or row["senha_hash"] != _hash(senha_atual):
        return jsonify({"ok": False, "error": "Senha atual incorreta"}), 401

    conn.execute(
        "UPDATE usuarios SET senha_hash=?,atualizado_em=datetime('now','localtime') WHERE id=?",
        (_hash(senha_nova), uid),
    )
    conn.commit()
    return jsonify({"ok": True, "mensagem": "Senha alterada com sucesso"})


# ── Health ────────────────────────────────────────────

@bp.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True})


@bp.route("/api/health", methods=["GET"])
def health():
    try:
        get_db().execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({"status": "ok" if db_ok else "degraded", "db": db_ok})
