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
    
    # Check if migration is needed
    table_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'").fetchone()
    if table_exists:
        schema_row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='usuarios'").fetchone()
        schema_sql = schema_row["sql"] if schema_row else ""
        if "admin" in schema_sql or "operador" in schema_sql or "leitor" in schema_sql:
            try:
                conn.execute("ALTER TABLE usuarios RENAME TO usuarios_old")
                conn.execute("""CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    email TEXT DEFAULT '',
                    login TEXT NOT NULL UNIQUE,
                    senha_hash TEXT NOT NULL,
                    nivel TEXT NOT NULL DEFAULT 'padrao'
                        CHECK (nivel IN ('adm','padrao')),
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT DEFAULT (datetime('now','localtime')),
                    atualizado_em TEXT DEFAULT (datetime('now','localtime'))
                )""")
                conn.execute("""
                    INSERT INTO usuarios (id, nome, email, login, senha_hash, nivel, ativo, criado_em, atualizado_em)
                    SELECT id, nome, email, login, senha_hash,
                           CASE WHEN nivel = 'admin' THEN 'adm' ELSE 'padrao' END,
                           ativo, criado_em, atualizado_em
                    FROM usuarios_old
                """)
                conn.execute("DROP TABLE usuarios_old")
                conn.commit()
            except Exception as e:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                # Se falhar, tenta apenas atualizar os níveis na tabela atual
                try:
                    conn.execute("UPDATE usuarios SET nivel='adm' WHERE nivel='admin'")
                    conn.execute("UPDATE usuarios SET nivel='padrao' WHERE nivel IN ('operador', 'leitor')")
                    conn.commit()
                except Exception:
                    pass
    else:
        conn.execute("""CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT DEFAULT '',
            login TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            nivel TEXT NOT NULL DEFAULT 'padrao'
                CHECK (nivel IN ('adm','padrao')),
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT DEFAULT (datetime('now','localtime')),
            atualizado_em TEXT DEFAULT (datetime('now','localtime'))
        )""")
        conn.commit()


def _seed_admin(admin_password, app):
    if not admin_password:
        return
    conn = app._get_db()
    conn.execute("DELETE FROM usuarios WHERE login IN ('admin', 'administrador')")
    conn.commit()
    
    row = conn.execute("SELECT id FROM usuarios WHERE login='aleksandro' AND ativo=1").fetchone()
    if row:
        conn.execute("UPDATE usuarios SET nivel='adm' WHERE login='aleksandro'")
        conn.commit()
    else:
        conn.execute(
            "INSERT INTO usuarios (nome,email,login,senha_hash,nivel,ativo) VALUES (?,?,?,?,?,1)",
            ("Aleksandro", "aleksandro@inaja.pr.gov.br", "aleksandro", _hash(admin_password), "adm"),
        )
        conn.commit()

    # Garantir usuário Maicon como padrão
    row_maicon = conn.execute("SELECT id FROM usuarios WHERE login='maicon'").fetchone()
    if row_maicon:
        conn.execute("UPDATE usuarios SET nivel='padrao' WHERE login='maicon'")
    else:
        conn.execute(
            "INSERT INTO usuarios (nome,email,login,senha_hash,nivel,ativo) VALUES (?,?,?,?,?,1)",
            ("Maicon", "maicon@inaja.pr.gov.br", "maicon", _hash("Inaja@2025!"), "padrao"),
        )

    # Garantir usuário Luana como padrão
    row_luana = conn.execute("SELECT id FROM usuarios WHERE login='luana'").fetchone()
    if row_luana:
        conn.execute("UPDATE usuarios SET nivel='padrao' WHERE login='luana'")
    else:
        conn.execute(
            "INSERT INTO usuarios (nome,email,login,senha_hash,nivel,ativo) VALUES (?,?,?,?,?,1)",
            ("Luana", "luana@inaja.pr.gov.br", "luana", _hash("Inaja@2025!"), "padrao"),
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
    from flask import current_app
    d = request.get_json(force=True) or {}
    login_input = (d.get("login") or "").strip().lower()
    senha = d.get("senha") or ""

    if not login_input or not senha:
        return jsonify({"ok": False, "error": "Informe login e senha"}), 400

    ip = request.remote_addr or "unknown"
    if rate_limited(f"login:{ip}", max_hits=10, window=60):
        current_app.logger.warning("Tentativa de login bloqueada por rate limit para o IP %s", ip)
        return jsonify({"ok": False, "error": "Muitas tentativas. Aguarde 1 minuto."}), 429

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE login=? AND ativo=1", (login_input,)
    ).fetchone()

    if not row or row["senha_hash"] != _hash(senha):
        current_app.logger.warning("Falha na tentativa de login para o usuário '%s' a partir do IP %s", login_input, ip)
        return jsonify({"ok": False, "error": "Login ou senha invalidos"}), 401

    session["usuario_id"] = row["id"]
    session["usuario_login"] = row["login"]
    session["usuario_nome"] = row["nome"]
    # Normaliza nivel da sessão para aceitar 'admin' ou 'adm'
    session["usuario_nivel"] = "admin" if row["nivel"] == "adm" else "padrao"
    session.permanent = False

    current_app.logger.info("Usuário '%s' (Nível: %s) autenticado com sucesso a partir do IP %s", row["login"], row["nivel"], ip)

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
    from flask import current_app
    user_login = session.get("usuario_login") or "Anonymous"
    for k in ("usuario_id", "usuario_login", "usuario_nome", "usuario_nivel"):
        session.pop(k, None)
    ip = request.remote_addr or "unknown"
    current_app.logger.info("Usuário '%s' deslogou (IP %s)", user_login, ip)
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
    conn.execute("DELETE FROM usuarios WHERE login IN ('admin', 'administrador')")
    conn.commit()
    
    row = conn.execute("SELECT * FROM usuarios WHERE login='aleksandro' AND ativo=1").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO usuarios (nome,email,login,senha_hash,nivel,ativo) VALUES (?,?,?,?,?,1)",
            ("Aleksandro", "aleksandro@inaja.pr.gov.br", "aleksandro", _hash(admin_password), "adm"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM usuarios WHERE login='aleksandro' AND ativo=1").fetchone()

    session["usuario_id"] = row["id"]
    session["usuario_login"] = row["login"]
    session["usuario_nome"] = row["nome"]
    session["usuario_nivel"] = "admin"
    session.permanent = False
    return jsonify({"ok": True})


# ── CRUD de usuarios (admin only) ────────────────────

@bp.route("/api/auth/usuarios", methods=["GET"])
def listar_usuarios():
    if "usuario_id" not in session or session.get("usuario_nivel") not in ("admin", "adm"):
        return jsonify({"error": "Nao autorizado"}), 403
    rows = get_db().execute(
        "SELECT * FROM usuarios ORDER BY ativo DESC, nome ASC"
    ).fetchall()
    return jsonify([_usuario_to_dict(r) for r in rows])


@bp.route("/api/auth/usuarios", methods=["POST"])
def criar_usuario():
    if session.get("usuario_nivel") not in ("admin", "adm"):
        return jsonify({"error": "Nao autorizado"}), 403
    d = request.get_json(force=True) or {}
    nome = (d.get("nome") or "").strip()
    email = (d.get("email") or "").strip()
    login = (d.get("login") or "").strip().lower()
    senha = d.get("senha") or ""
    nivel = (d.get("nivel") or "padrao").strip().lower()

    # Normalização
    if nivel in ("admin", "adm"):
        nivel = "adm"
    else:
        nivel = "padrao"

    errs = []
    if not nome: errs.append("Nome obrigatorio")
    if not login or len(login) < 3: errs.append("Login deve ter 3+ caracteres")
    if not senha or len(senha) < 4: errs.append("Senha deve ter 4+ caracteres")
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
    if session.get("usuario_nivel") not in ("admin", "adm"):
        return jsonify({"error": "Nao autorizado"}), 403
    d = request.get_json(force=True) or {}
    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    if not row:
        return jsonify({"error": "Usuario nao encontrado"}), 404

    nome = (d.get("nome") or row["nome"]).strip()
    email = (d.get("email") if d.get("email") is not None else (row["email"] or "")).strip()
    login = (d.get("login") or row["login"]).strip().lower()
    nivel = (d.get("nivel") or row["nivel"]).strip().lower()
    ativo = d.get("ativo", bool(row["ativo"]))

    if nivel in ("admin", "adm"):
        nivel = "adm"
    else:
        nivel = "padrao"

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
    if session.get("usuario_nivel") not in ("admin", "adm"):
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
    from flask import current_app
    if "usuario_id" not in session:
        return jsonify({"error": "Nao autenticado"}), 401
    d = request.get_json(force=True) or {}
    senha_atual = d.get("senha_atual", "")
    senha_nova = d.get("senha_nova", "")

    ip = request.remote_addr or "unknown"
    if not senha_atual or not senha_nova:
        return jsonify({"ok": False, "error": "Informe senha atual e nova senha"}), 400
    if len(senha_nova) < 4:
        return jsonify({"ok": False, "error": "Nova senha deve ter 4+ caracteres"}), 400

    conn = get_db()
    uid = session["usuario_id"]
    row = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    if not row or row["senha_hash"] != _hash(senha_atual):
        current_app.logger.warning("Falha ao alterar senha: senha atual incorreta para o usuário '%s' (IP %s)", session.get("usuario_login"), ip)
        return jsonify({"ok": False, "error": "Senha atual incorreta"}), 401

    conn.execute(
        "UPDATE usuarios SET senha_hash=?,atualizado_em=datetime('now','localtime') WHERE id=?",
        (_hash(senha_nova), uid),
    )
    conn.commit()
    current_app.logger.info("Senha alterada com sucesso para o usuário '%s' (IP %s)", row["login"], ip)
    return jsonify({"ok": True, "mensagem": "Senha alterada com sucesso"})


# ── Health ────────────────────────────────────────────

@bp.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True})


@bp.route("/api/health", methods=["GET"])
def health():
    import time
    from flask import current_app
    try:
        get_db().execute("SELECT 1").fetchone()
        db_ok = True
    except Exception as e:
        db_ok = False
        current_app.logger.error("Erro na conectividade do banco de dados no Health Check: %s", str(e))

    startup_time = current_app.config.get("STARTUP_TIME", time.time())
    uptime_s = int(time.time() - startup_time)
    
    error_count = getattr(current_app, "error_count", 0)
    slow_requests = getattr(current_app, "slow_request_count", 0)

    return jsonify({
        "status": "ok" if (db_ok and error_count < 10) else "degraded",
        "db": db_ok,
        "uptime_s": uptime_s,
        "error_count": error_count,
        "slow_requests": slow_requests,
        "cache_files": len(getattr(current_app, "file_cache", {})),
        "cache_gzip": len(getattr(current_app, "gzip_cache", {}))
    })
