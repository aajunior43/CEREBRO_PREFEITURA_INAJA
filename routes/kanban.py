"""Blueprint: Kanban (tarefas, IA, anexos)"""

import json
import re
from collections import defaultdict
from flask import Blueprint, request, jsonify, send_file
from io import BytesIO as _io

bp = Blueprint("kanban", __name__)


def get_db():
    from flask import g

    return g._get_db()


def row_to_dict(row):
    return dict(row)


def _normalize_status(value: str) -> str:
    value = (value or "").strip().lower()
    aliases = {
        "todo": "todo",
        "a fazer": "todo",
        "afazer": "todo",
        "to do": "todo",
        "in-progress": "in-progress",
        "in progress": "in-progress",
        "em progresso": "in-progress",
        "progress": "in-progress",
        "done": "done",
        "concluido": "done",
        "concluído": "done",
        "finalizado": "done",
    }
    return aliases.get(value, "todo")


def _normalize_priority(value: str) -> str:
    value = (value or "").strip().lower()
    aliases = {
        "high": "high",
        "alta": "high",
        "medium": "medium",
        "media": "medium",
        "média": "medium",
        "low": "low",
        "baixa": "low",
    }
    return aliases.get(value, "medium")


def _sanitize_task(task: dict) -> dict:
    return {
        "title": (task.get("title") or "").strip(),
        "description": (task.get("description") or "").strip(),
        "status": _normalize_status(task.get("status") or "todo"),
        "priority": _normalize_priority(task.get("priority") or "medium"),
    }


def _get_openrouter_config(conn, api_key_override: str = "", model_override: str = ""):
    from config import settings

    rows = conn.execute(
        "SELECT chave, valor FROM configuracoes WHERE chave IN (?,?)",
        ("api_openrouter_key", "api_openrouter_modelo"),
    ).fetchall()
    cfg = {row["chave"]: (row["valor"] or "").strip() for row in rows}
    api_key = (
        (api_key_override or "").strip()
        or cfg.get("api_openrouter_key", "")
        or (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    )
    raw_model = (
        (model_override or "").strip()
        or cfg.get("api_openrouter_modelo", "")
        or (os.environ.get("OPENROUTER_MODEL") or "").strip()
        or settings.openrouter_default_model
    )
    model = (
        raw_model.strip()
        if not raw_model.endswith(":free") and raw_model != "openrouter/free"
        else raw_model.strip()
    )
    return api_key, model


import os


def _build_ai_service(api_key: str, model: str):
    from config import settings
    from services.openrouter_service import build_openrouter_service

    return build_openrouter_service(
        api_key=api_key,
        default_model=model or settings.openrouter_default_model,
        referer=settings.openrouter_referer,
        title=settings.openrouter_title,
        logger=None,
        timeout_seconds=settings.openrouter_timeout_seconds,
        max_retries=settings.openrouter_max_retries,
        backoff_base=settings.openrouter_backoff_base,
        cache_ttl_seconds=settings.openrouter_cache_ttl_seconds,
    )


def _extract_json_block(text: str):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return json.loads(match.group(1))
    start_obj, end_obj = text.find("{"), text.rfind("}")
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        try:
            return json.loads(text[start_obj : end_obj + 1])
        except Exception:
            pass
    start_arr, end_arr = text.find("["), text.rfind("]")
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        return json.loads(text[start_arr : end_arr + 1])
    raise ValueError("Formato inválido")


def _kanban_ai_completion(
    action: str,
    user_prompt: str,
    task: dict | None = None,
    api_key_override: str = "",
    model_override: str = "",
    status_hint: str = "",
    priority_hint: str = "",
):
    from services.openrouter_service import AIServiceError
    import datetime

    conn = get_db()
    api_key, model = _get_openrouter_config(conn, api_key_override, model_override)
    if not api_key:
        return None, ("Chave do OpenRouter não configurada.", 400)
    today = datetime.date.today().strftime("%d/%m/%Y")
    hints = ""
    if status_hint:
        hints += f' O status deve ser "{status_hint}".'
    if priority_hint:
        hints += f' A prioridade deve ser "{priority_hint}".'
    system_map = {
        "create": (
            f"Você é um assistente Kanban da Prefeitura de Inajá. Hoje é {today}. "
            f"Crie uma tarefa bem estruturada. Responda APENAS com JSON: "
            f'"title","description","status"(todo|in-progress|done),"priority"(low|medium|high). '
            f"{hints} Português do Brasil."
        ),
        "improve": (
            f"Você é um assistente Kanban da Prefeitura de Inajá. Hoje é {today}. "
            f"Melhore a tarefa. Responda APENAS com JSON: "
            f'"title","description","status","priority". Português do Brasil.'
        ),
        "breakdown": (
            f"Você é um assistente Kanban da Prefeitura de Inajá. Hoje é {today}. "
            f"Quebre em subtarefas. JSON: "
            f'{{"tasks":[{{"title":"","description":"","status":"todo","priority":"medium"}}]}}. '
            f"3 a 7 subtarefas. Português do Brasil."
        ),
        "plan": (
            f"Você é um assistente Kanban da Prefeitura de Inajá. Hoje é {today}. "
            f"Gere um plano de ação. JSON: "
            f'{{"task":{{"title":"","description":"","status":"todo","priority":"medium"}},'
            f'"summary":"","next_action":"","checklist":[""],'
            f'"subtarefas":[{{"title":"","description":"","status":"todo","priority":"medium"}}]}}. '
            f"Português do Brasil."
        ),
        "classify": (
            f"Você é um classificador de tarefas da Prefeitura de Inajá. Hoje é {today}. "
            f"JSON: "
            f'{{"categoria_ia":"financeiro|documento|prazo|auditoria|protocolo","confianca":0.0,"justificativa":""}}. '
            f"Português do Brasil."
        ),
        "stale": (
            f"Você é um assistente de gestão de tarefas. Hoje é {today}. "
            f"JSON: "
            f'{{"status":"normal|atencao|parada","dias_sem_atualizacao":0,"resumo":"","sugestoes":[""]}}. '
            f"Português do Brasil."
        ),
        "professional_rewrite": (
            f"Reescreva a tarefa em tom profissional. JSON: "
            f'"title","description","status","priority". Português do Brasil.'
        ),
    }
    messages = [
        {"role": "system", "content": system_map.get(action, system_map["improve"])}
    ]
    if task:
        messages.append(
            {
                "role": "user",
                "content": f"Tarefa:\n{json.dumps(task, ensure_ascii=False)}\n\nPedido:\n{user_prompt}",
            }
        )
    else:
        messages.append({"role": "user", "content": user_prompt})
    try:
        response = _build_ai_service(api_key, model).chat_by_task(
            task_type="chat",
            messages=messages,
            temperature=0.4,
            max_tokens=900,
            use_cache=False,
            metadata={"feature": "kanban_ai", "action": action},
        )
        return _extract_json_block(response.text), None
    except AIServiceError as err:
        return None, (err.user_message, err.status_code)
    except Exception as err:
        return None, (str(err), 500)


# ── CRUD ─────────────────────────────────────────────────────
@bp.route("/api/kanban", methods=["GET"])
def kanban_listar():
    try:
        limit = max(1, min(request.args.get("limit", 200, type=int), 2000))
        offset = max(0, request.args.get("offset", 0, type=int))
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) AS total FROM kanban_tasks").fetchone()[
            "total"
        ]
        rows = conn.execute(
            "SELECT id,title,description,status,priority,categoria,data_vencimento,responsavel,concluido_em,criado_em,atualizado_em "
            "FROM kanban_tasks ORDER BY atualizado_em DESC, criado_em DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        tasks = [row_to_dict(r) for r in rows]
        task_ids = [t["id"] for t in tasks]
        attachments_by_task = defaultdict(list)
        if task_ids:
            placeholders = ",".join("?" for _ in task_ids)
            for row in conn.execute(
                f"SELECT id,task_id,file_name,mime_type,file_size,criado_em FROM kanban_attachments WHERE task_id IN ({placeholders}) ORDER BY criado_em DESC, id DESC",
                task_ids,
            ).fetchall():
                attachments_by_task[row_to_dict(row)["task_id"]].append(
                    row_to_dict(row)
                )
        for task in tasks:
            task["attachments"] = attachments_by_task.get(task["id"], [])
        return jsonify(
            {"items": tasks, "total": total, "limit": limit, "offset": offset}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban", methods=["POST"])
def kanban_criar():
    try:
        data = request.get_json(force=True) or {}
        task_id = (data.get("id") or "").strip()
        title = (data.get("title") or "").strip()
        if not task_id:
            return jsonify({"error": "id é obrigatório"}), 400
        if not title:
            return jsonify({"error": "title é obrigatório"}), 400
        status = _normalize_status(data.get("status") or "todo")
        priority = _normalize_priority(data.get("priority") or "medium")
        concluido_em = _time.strftime("%Y-%m-%d %H:%M:%S") if status == "done" else ""
        import time as _time

        conn = get_db()
        conn.execute(
            "INSERT INTO kanban_tasks (id,title,description,status,priority,categoria,data_vencimento,responsavel,concluido_em,criado_em,atualizado_em) "
            "VALUES (?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))",
            (
                task_id,
                title,
                (data.get("description") or "").strip(),
                status,
                priority,
                (data.get("categoria") or "").strip().upper(),
                (data.get("data_vencimento") or "").strip(),
                (data.get("responsavel") or "").strip(),
                concluido_em,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id,title,description,status,priority,categoria,data_vencimento,responsavel,concluido_em,criado_em,atualizado_em FROM kanban_tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception:
        import sqlite3

        return jsonify({"error": "Já existe uma tarefa com esse id"}), 409


@bp.route("/api/kanban/<task_id>", methods=["PUT"])
def kanban_atualizar(task_id):
    try:
        import time as _time

        data = request.get_json(force=True) or {}
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title é obrigatório"}), 400
        status = _normalize_status(data.get("status") or "todo")
        priority = _normalize_priority(data.get("priority") or "medium")
        conn = get_db()
        current = conn.execute(
            "SELECT status,concluido_em FROM kanban_tasks WHERE id=?", (task_id,)
        ).fetchone()
        if not current:
            return jsonify({"error": "Tarefa não encontrada"}), 404
        concluido_em = current["concluido_em"] or ""
        if status == "done" and current["status"] != "done":
            concluido_em = _time.strftime("%Y-%m-%d %H:%M:%S")
        elif status != "done":
            concluido_em = ""
        conn.execute(
            "UPDATE kanban_tasks SET title=?,description=?,status=?,priority=?,categoria=?,data_vencimento=?,responsavel=?,concluido_em=?,atualizado_em=datetime('now','localtime') WHERE id=?",
            (
                title,
                (data.get("description") or "").strip(),
                status,
                priority,
                (data.get("categoria") or "").strip().upper(),
                (data.get("data_vencimento") or "").strip(),
                (data.get("responsavel") or "").strip(),
                concluido_em,
                task_id,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id,title,description,status,priority,categoria,data_vencimento,responsavel,concluido_em,criado_em,atualizado_em FROM kanban_tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        return jsonify(row_to_dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban/<task_id>", methods=["DELETE"])
def kanban_excluir(task_id):
    try:
        conn = get_db()
        cur = conn.execute("DELETE FROM kanban_tasks WHERE id=?", (task_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Tarefa não encontrada"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── IA ───────────────────────────────────────────────────────
def _handle_ai_result(parsed, error, sanitizer):
    if error:
        return jsonify({"error": error[0]}), error[1]
    result = sanitizer(parsed if isinstance(parsed, dict) else {})
    if isinstance(result, dict) and not result.get("title"):
        return jsonify({"error": "A IA não retornou um título válido"}), 502
    return jsonify(result)


@bp.route("/api/kanban/ai/create-from-text", methods=["POST"])
def ai_create():
    try:
        data = request.get_json(force=True) or {}
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return jsonify({"error": "Informe o texto"}), 400
        parsed, error = _kanban_ai_completion(
            "create",
            prompt,
            api_key_override=(data.get("api_key") or "").strip(),
            model_override=(data.get("model") or "").strip(),
            status_hint=(data.get("status_hint") or "").strip(),
            priority_hint=(data.get("priority_hint") or "").strip(),
        )
        return _handle_ai_result(parsed, error, _sanitize_task)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban/ai/improve-task", methods=["POST"])
def ai_improve():
    try:
        data = request.get_json(force=True) or {}
        task = data.get("task") or {}
        if not isinstance(task, dict) or not (task.get("title") or "").strip():
            return jsonify({"error": "Envie uma tarefa válida"}), 400
        parsed, error = _kanban_ai_completion(
            "improve",
            (data.get("prompt") or "").strip(),
            _sanitize_task(task),
            api_key_override=(data.get("api_key") or "").strip(),
            model_override=(data.get("model") or "").strip(),
        )
        return _handle_ai_result(parsed, error, _sanitize_task)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban/ai/breakdown-task", methods=["POST"])
def ai_breakdown():
    try:
        data = request.get_json(force=True) or {}
        task = data.get("task") or {}
        if not isinstance(task, dict) or not (task.get("title") or "").strip():
            return jsonify({"error": "Envie uma tarefa válida"}), 400
        parsed, error = _kanban_ai_completion(
            "breakdown",
            (data.get("prompt") or "").strip(),
            _sanitize_task(task),
            api_key_override=(data.get("api_key") or "").strip(),
            model_override=(data.get("model") or "").strip(),
        )
        if error:
            return jsonify({"error": error[0]}), error[1]
        items = parsed.get("tasks") if isinstance(parsed, dict) else parsed
        if not isinstance(items, list):
            return jsonify({"error": "Lista inválida"}), 502
        tasks = [
            _sanitize_task(item)
            for item in items
            if isinstance(item, dict) and (item.get("title") or "").strip()
        ]
        if not tasks:
            return jsonify({"error": "A IA não gerou subtarefas válidas"}), 502
        return jsonify({"tasks": tasks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban/ai/plan-task", methods=["POST"])
def ai_plan():
    try:
        data = request.get_json(force=True) or {}
        task = data.get("task") or {}
        if not isinstance(task, dict) or not (task.get("title") or "").strip():
            return jsonify({"error": "Envie uma tarefa válida"}), 400
        parsed, error = _kanban_ai_completion(
            "plan",
            (data.get("prompt") or "").strip(),
            {
                **_sanitize_task(task),
                "title": (task.get("title") or "").strip(),
                "categoria": (task.get("categoria") or "").strip().upper(),
                "data_vencimento": (task.get("data_vencimento") or "").strip(),
                "responsavel": (task.get("responsavel") or "").strip(),
            },
            api_key_override=(data.get("api_key") or "").strip(),
            model_override=(data.get("model") or "").strip(),
        )
        if error:
            return jsonify({"error": error[0]}), error[1]
        plan = parsed if isinstance(parsed, dict) else {}
        base = _sanitize_task(plan.get("task") or {})
        if not base["title"]:
            return jsonify({"error": "Tarefa principal inválida"}), 502
        return jsonify(
            {
                "task": base,
                "summary": plan.get("summary", ""),
                "next_action": plan.get("next_action", ""),
                "checklist": plan.get("checklist", [])[:8],
                "subtarefas": [
                    _sanitize_task(s)
                    for s in (plan.get("subtarefas") or [])[:6]
                    if isinstance(s, dict)
                ],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban/ai/classify-task", methods=["POST"])
def ai_classify():
    try:
        data = request.get_json(force=True) or {}
        task = data.get("task") or {}
        if not isinstance(task, dict) or not (task.get("title") or "").strip():
            return jsonify({"error": "Envie uma tarefa válida"}), 400
        parsed, error = _kanban_ai_completion(
            "classify",
            (data.get("prompt") or "Classifique esta tarefa.").strip(),
            {
                **_sanitize_task(task),
                "title": (task.get("title") or "").strip(),
                "categoria": (task.get("categoria") or "").strip().upper(),
                "data_vencimento": (task.get("data_vencimento") or "").strip(),
                "responsavel": (task.get("responsavel") or "").strip(),
            },
            api_key_override=(data.get("api_key") or "").strip(),
            model_override=(data.get("model") or "").strip(),
        )
        if error:
            return jsonify({"error": error[0]}), error[1]
        p = parsed if isinstance(parsed, dict) else {}
        cat = str(p.get("categoria_ia") or p.get("categoria") or "").strip().lower()
        if cat not in {"financeiro", "documento", "prazo", "auditoria", "protocolo"}:
            cat = "documento"
        try:
            conf = max(0.0, min(1.0, float(p.get("confianca", 0))))
        except Exception:
            conf = 0.0
        return jsonify(
            {
                "categoria_ia": cat,
                "justificativa": str(p.get("justificativa") or "").strip(),
                "confianca": conf,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban/ai/stale-task", methods=["POST"])
def ai_stale():
    try:
        data = request.get_json(force=True) or {}
        task = data.get("task") or {}
        if not isinstance(task, dict) or not (task.get("title") or "").strip():
            return jsonify({"error": "Envie uma tarefa válida"}), 400
        parsed, error = _kanban_ai_completion(
            "stale",
            (data.get("prompt") or "Avalie se a tarefa está parada.").strip(),
            {
                **_sanitize_task(task),
                "title": (task.get("title") or "").strip(),
                "categoria": (task.get("categoria") or "").strip().upper(),
                "data_vencimento": (task.get("data_vencimento") or "").strip(),
                "responsavel": (task.get("responsavel") or "").strip(),
                "criado_em": (task.get("criado_em") or "").strip(),
                "atualizado_em": (task.get("atualizado_em") or "").strip(),
            },
            api_key_override=(data.get("api_key") or "").strip(),
            model_override=(data.get("model") or "").strip(),
        )
        if error:
            return jsonify({"error": error[0]}), error[1]
        p = parsed if isinstance(parsed, dict) else {}
        status = str(p.get("status") or "normal").strip().lower()
        if status not in {"normal", "atencao", "parada"}:
            status = "normal"
        try:
            dias = max(0, int(p.get("dias_sem_atualizacao", 0)))
        except Exception:
            dias = 0
        return jsonify(
            {
                "status": status,
                "dias_sem_atualizacao": dias,
                "resumo": str(p.get("resumo") or "").strip(),
                "sugestoes": [
                    str(s).strip()
                    for s in (p.get("sugestoes") or [])[:4]
                    if str(s).strip()
                ],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban/ai/professional-rewrite", methods=["POST"])
def ai_rewrite():
    try:
        data = request.get_json(force=True) or {}
        task = data.get("task") or {}
        if not isinstance(task, dict) or not (task.get("title") or "").strip():
            return jsonify({"error": "Envie uma tarefa válida"}), 400
        parsed, error = _kanban_ai_completion(
            "professional_rewrite",
            (data.get("prompt") or "Reescreva em tom profissional.").strip(),
            _sanitize_task(task),
            api_key_override=(data.get("api_key") or "").strip(),
            model_override=(data.get("model") or "").strip(),
        )
        return _handle_ai_result(parsed, error, _sanitize_task)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Anexos ───────────────────────────────────────────────────
@bp.route("/api/kanban/<task_id>/attachments", methods=["GET"])
def anexos_listar(task_id):
    try:
        conn = get_db()
        if not conn.execute(
            "SELECT id FROM kanban_tasks WHERE id=?", (task_id,)
        ).fetchone():
            return jsonify({"error": "Tarefa não encontrada"}), 404
        rows = conn.execute(
            "SELECT id,task_id,file_name,mime_type,file_size,criado_em FROM kanban_attachments WHERE task_id=? ORDER BY criado_em DESC, id DESC",
            (task_id,),
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban/<task_id>/attachments", methods=["POST"])
def anexos_enviar(task_id):
    file = request.files.get("arquivo")
    if not file or not file.filename:
        return jsonify({"error": "Arquivo é obrigatório"}), 400
    try:
        content = file.read()
        if not content:
            return jsonify({"error": "Arquivo vazio"}), 400
        if len(content) > 10 * 1024 * 1024:
            return jsonify({"error": "Arquivo excede 10 MB"}), 413
        conn = get_db()
        if not conn.execute(
            "SELECT id,title FROM kanban_tasks WHERE id=?", (task_id,)
        ).fetchone():
            return jsonify({"error": "Tarefa não encontrada"}), 404
        cur = conn.execute(
            "INSERT INTO kanban_attachments (task_id,file_name,mime_type,file_size,content,criado_em) VALUES (?,?,?,?,?,datetime('now','localtime'))",
            (
                task_id,
                file.filename,
                file.mimetype or "application/octet-stream",
                len(content),
                content,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id,task_id,file_name,mime_type,file_size,criado_em FROM kanban_attachments WHERE id=?",
            (cur.lastrowid,),
        ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route(
    "/api/kanban/<task_id>/attachments/<int:attachment_id>/download", methods=["GET"]
)
def anexo_download(task_id, attachment_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT id,task_id,file_name,mime_type,content FROM kanban_attachments WHERE id=? AND task_id=?",
            (attachment_id, task_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Anexo não encontrado"}), 404
        return send_file(
            _io.BytesIO(row["content"]),
            mimetype=row["mime_type"] or "application/octet-stream",
            as_attachment=True,
            download_name=row["file_name"],
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/kanban/<task_id>/attachments/<int:attachment_id>", methods=["DELETE"])
def anexo_excluir(task_id, attachment_id):
    try:
        conn = get_db()
        cur = conn.execute(
            "DELETE FROM kanban_attachments WHERE id=? AND task_id=?",
            (attachment_id, task_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Anexo não encontrado"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
