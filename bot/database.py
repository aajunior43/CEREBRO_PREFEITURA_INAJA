import sqlite3
import uuid
import asyncio
from datetime import date, timedelta
from typing import Optional, List, Dict, Any

from bot.config import DB_PATH, logger


# ==============================================================================
# DB HELPER
# ==============================================================================
def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


async def run_db(func, *args, **kwargs):
    """Executa a chamada síncrona do banco em uma thread separada para não bloquear o async event loop."""
    return await asyncio.to_thread(func, *args, **kwargs)


# ==============================================================================
# QUERIES SÍNCRONAS - KANBAN E GERAIS
# ==============================================================================
def _init_users_table():
    conn = _db_connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _get_user(telegram_id: str) -> Optional[Dict[str, Any]]:
    conn = _db_connect()
    try:
        row = conn.execute(
            "SELECT * FROM telegram_users WHERE telegram_id=?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _add_user(telegram_id: str, name: str) -> None:
    conn = _db_connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO telegram_users (telegram_id, name, status) VALUES (?, ?, 'pending')",
            (telegram_id, name),
        )
        conn.commit()
    finally:
        conn.close()


def _update_user_status(telegram_id: str, status: str) -> None:
    conn = _db_connect()
    try:
        conn.execute(
            "UPDATE telegram_users SET status=? WHERE telegram_id=?",
            (status, telegram_id),
        )
        conn.commit()
    finally:
        conn.close()


PRIO_ORDER = {"high": 0, "medium": 1, "low": 2}


def _listar_tarefas(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = _db_connect()
    try:
        if status_filter:
            rows = conn.execute(
                "SELECT id, title, description, status, priority, criado_em "
                "FROM kanban_tasks WHERE status=? ORDER BY criado_em DESC LIMIT 50",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, description, status, priority, criado_em "
                "FROM kanban_tasks ORDER BY criado_em DESC LIMIT 50"
            ).fetchall()
        tasks = [dict(r) for r in rows]
        tasks.sort(key=lambda t: PRIO_ORDER.get(t.get("priority", "medium"), 1))
        return tasks
    finally:
        conn.close()


def _criar_tarefa(
    title: str, description: str, status: str, priority: str
) -> Dict[str, Any]:
    task_id = str(uuid.uuid4())
    conn = _db_connect()
    try:
        conn.execute(
            "INSERT INTO kanban_tasks (id, title, description, status, priority, "
            "criado_em, atualizado_em) VALUES (?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))",
            (task_id, title, description, status, priority),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, title, description, status, priority, criado_em FROM kanban_tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def _buscar_tarefas(termo: str) -> List[Dict[str, Any]]:
    conn = _db_connect()
    try:
        like = f"%{termo}%"
        rows = conn.execute(
            "SELECT id, title, description, status, priority, criado_em "
            "FROM kanban_tasks WHERE title LIKE ? OR description LIKE ? "
            "ORDER BY criado_em DESC LIMIT 20",
            (like, like),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _buscar_protocolos(termo: str) -> List[Dict[str, Any]]:
    conn = _db_connect()
    try:
        like = f"%{termo.lower()}%"
        rows = conn.execute(
            "SELECT id, numero, tipo, direcao, origem_destino, assunto, data_protocolo, status "
            "FROM protocolos WHERE LOWER(numero) LIKE ? OR LOWER(assunto) LIKE ? OR LOWER(origem_destino) LIKE ? "
            "ORDER BY id DESC LIMIT 20",
            (like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _buscar_despesas(termo: str) -> List[Dict[str, Any]]:
    conn = _db_connect()
    try:
        like = f"%{termo.lower()}%"
        rows = conn.execute(
            "SELECT id, importacao_id, dados "
            "FROM despesas_linhas WHERE LOWER(dados) LIKE ? "
            "ORDER BY id DESC LIMIT 20",
            (like,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _analise_financeira(ano: int, mes: int) -> Dict[str, Any]:
    conn = _db_connect()
    try:
        credores = conn.execute(
            "SELECT id, nome, valor, tipo_valor FROM credores WHERE ativo=1 ORDER BY valor DESC"
        ).fetchall()
        credores = [dict(c) for c in credores]

        emp_rows = conn.execute(
            "SELECT credor_id FROM empenhos WHERE ano=? AND mes=? AND empenhado=1",
            (ano, mes),
        ).fetchall()
        empenhados_ids = {r["credor_id"] for r in emp_rows}

        lista_emp = []
        lista_pend = []
        total_previsto = 0.0
        total_empenhado = 0.0

        for c in credores:
            v = float(c["valor"] or 0)
            total_previsto += v
            if c["id"] in empenhados_ids:
                total_empenhado += v
                lista_emp.append({"nome": c["nome"], "valor": v})
            else:
                lista_pend.append({"nome": c["nome"], "valor": v})

        total_pendente = total_previsto - total_empenhado
        pct = (total_empenhado / total_previsto * 100) if total_previsto > 0 else 0.0

        top5 = sorted(credores, key=lambda x: float(x["valor"] or 0), reverse=True)[:5]

        mes_str_a = f"{mes:02d}/{ano}"
        mes_str_b = f"{ano}-{mes:02d}"
        rpas = conn.execute(
            "SELECT COUNT(*) AS qtd, COALESCE(SUM(valor_bruto), 0) AS total_bruto "
            "FROM rpas WHERE periodo_referencia LIKE ? OR periodo_referencia LIKE ?",
            (f"%{mes_str_a}%", f"%{mes_str_b}%"),
        ).fetchone()
        rpas_qtd = rpas["qtd"] if rpas else 0
        rpas_total = float(rpas["total_bruto"] if rpas else 0)

        mes_ant = mes - 1 if mes > 1 else 12
        ano_ant = ano if mes > 1 else ano - 1
        emp_ant = conn.execute(
            "SELECT COUNT(*) AS qtd FROM empenhos WHERE ano=? AND mes=? AND empenhado=1",
            (ano_ant, mes_ant),
        ).fetchone()
        qtd_ant = emp_ant["qtd"] if emp_ant else 0

        ids_ant = {
            r["credor_id"]
            for r in conn.execute(
                "SELECT credor_id FROM empenhos WHERE ano=? AND mes=? AND empenhado=1",
                (ano_ant, mes_ant),
            ).fetchall()
        }
        val_ant = sum(float(c["valor"] or 0) for c in credores if c["id"] in ids_ant)

        return {
            "ano": ano,
            "mes": mes,
            "total_credores": len(credores),
            "total_previsto": total_previsto,
            "total_empenhado": total_empenhado,
            "total_pendente": total_pendente,
            "pct_empenhado": pct,
            "qtd_empenhados": len(lista_emp),
            "qtd_pendentes": len(lista_pend),
            "empenhados": sorted(lista_emp, key=lambda x: x["valor"], reverse=True),
            "pendentes": sorted(lista_pend, key=lambda x: x["valor"], reverse=True),
            "top5_valores": [
                {"nome": c["nome"], "valor": float(c["valor"] or 0)} for c in top5
            ],
            "rpas_qtd": rpas_qtd,
            "rpas_total": rpas_total,
            "mes_anterior": {
                "mes": mes_ant,
                "ano": ano_ant,
                "qtd_empenhados": qtd_ant,
                "total_empenhado": val_ant,
            },
        }
    finally:
        conn.close()


# ==============================================================================
# WRAPPERS ASSÍNCRONOS
# ==============================================================================


async def db_listar_tarefas(status_filter: Optional[str] = None):
    return await run_db(_listar_tarefas, status_filter)


async def db_criar_tarefa(title: str, description: str, status: str, priority: str):
    return await run_db(_criar_tarefa, title, description, status, priority)


async def db_buscar_tarefas(termo: str):
    return await run_db(_buscar_tarefas, termo)


async def db_buscar_protocolos(termo: str):
    return await run_db(_buscar_protocolos, termo)


async def db_buscar_despesas(termo: str):
    return await run_db(_buscar_despesas, termo)


async def db_analise_financeira(ano: int, mes: int):
    return await run_db(_analise_financeira, ano, mes)


def _atualizar_status_tarefa(task_id: str, novo_status: str):
    conn = _db_connect()
    try:
        conn.execute(
            "UPDATE kanban_tasks SET status=?, atualizado_em=datetime('now','localtime') WHERE id=?",
            (novo_status, task_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, title, status, priority FROM kanban_tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _contar_credores():
    conn = _db_connect()
    try:
        ativos = conn.execute("SELECT COUNT(*) FROM credores WHERE ativo=1").fetchone()[
            0
        ]
        inativos = conn.execute(
            "SELECT COUNT(*) FROM credores WHERE ativo=0"
        ).fetchone()[0]
        return {"ativos": ativos, "inativos": inativos, "total": ativos + inativos}
    finally:
        conn.close()


def _logs_recentes(limite: int = 10):
    conn = _db_connect()
    try:
        rows = conn.execute(
            "SELECT acao, credor_nome, detalhes, data FROM logs ORDER BY data DESC LIMIT ?",
            (limite,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _toggle_empenho(credor_id: int, ano: int, mes: int) -> dict:
    """Marca/desmarca empenho de um credor. Retorna {action: 'created'|'removed', credor_nome}."""
    conn = _db_connect()
    try:
        existing = conn.execute(
            "SELECT * FROM empenhos WHERE credor_id=? AND ano=? AND mes=?",
            (credor_id, ano, mes),
        ).fetchone()

        credor = conn.execute(
            "SELECT nome FROM credores WHERE id=?", (credor_id,)
        ).fetchone()
        nome = credor["nome"] if credor else str(credor_id)

        if existing:
            conn.execute("DELETE FROM empenhos WHERE id=?", (existing["id"],))
            conn.execute(
                "INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?, ?, ?, ?)",
                ("EMPENHO_REMOVE", credor_id, nome, f"Removido empenho {ano}/{mes}"),
            )
            conn.commit()
            return {"action": "removed", "credor_nome": nome}
        else:
            conn.execute(
                "INSERT INTO empenhos (credor_id, ano, mes, empenhado, timestamp) VALUES (?, ?, ?, 1, datetime('now', 'localtime'))",
                (credor_id, ano, mes),
            )
            conn.execute(
                "INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?, ?, ?, ?)",
                ("EMPENHO_CREATE", credor_id, nome, f"Empenhado {ano}/{mes}"),
            )
            conn.commit()
            return {"action": "created", "credor_nome": nome}
    finally:
        conn.close()


def _listar_pendentes_com_id(ano: int, mes: int) -> list:
    """Lista credores pendentes com seus IDs para ação rápida."""
    conn = _db_connect()
    try:
        credores = conn.execute(
            "SELECT id, nome, valor, tipo_valor FROM credores WHERE ativo=1 ORDER BY valor DESC"
        ).fetchall()
        credores = [dict(c) for c in credores]

        emp_rows = conn.execute(
            "SELECT credor_id FROM empenhos WHERE ano=? AND mes=? AND empenhado=1",
            (ano, mes),
        ).fetchall()
        empenhados_ids = {r["credor_id"] for r in emp_rows}

        pendentes = []
        for c in credores:
            if c["id"] not in empenhados_ids:
                pendentes.append(
                    {"id": c["id"], "nome": c["nome"], "valor": float(c["valor"] or 0)}
                )

        return pendentes[:20]
    finally:
        conn.close()


async def db_toggle_empenho(credor_id: int, ano: int, mes: int) -> dict:
    return await run_db(_toggle_empenho, credor_id, ano, mes)


async def db_listar_pendentes_com_id(ano: int, mes: int) -> list:
    return await run_db(_listar_pendentes_com_id, ano, mes)


async def db_tarefas_proximas_vencimento(dias: int = 7):
    return await run_db(_tarefas_proximas_vencimento, dias)


async def db_atualizar_status_tarefa(task_id: str, novo_status: str):
    return await run_db(_atualizar_status_tarefa, task_id, novo_status)


def _listar_credores_ativos():
    conn = _db_connect()
    try:
        rows = conn.execute(
            "SELECT id, nome, valor, departamento FROM credores WHERE ativo=1 ORDER BY nome"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


async def db_listar_credores_ativos():
    return await run_db(_listar_credores_ativos)


async def db_contar_credores():
    return await run_db(_contar_credores)


async def db_logs_recentes(limite: int = 10):
    return await run_db(_logs_recentes, limite)


async def db_init_users_table():
    return await run_db(_init_users_table)


async def db_get_user(telegram_id: str):
    return await run_db(_get_user, telegram_id)


async def db_add_user(telegram_id: str, name: str):
    return await run_db(_add_user, telegram_id, name)


async def db_update_user_status(telegram_id: str, status: str):
    return await run_db(_update_user_status, telegram_id, status)
