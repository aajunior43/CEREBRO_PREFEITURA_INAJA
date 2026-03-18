import io as _io
import json
import re
import sqlite3
import time as _time
from collections import defaultdict

from flask import Blueprint, request, jsonify, send_file, current_app
from config import settings
from database import get_db, row_to_dict
from services.openrouter_service import AIServiceError

bp = Blueprint('kanban', __name__)


def _normalize_kanban_status(value: str) -> str:
    value = (value or '').strip().lower()
    aliases = {
        'todo': 'todo',
        'a fazer': 'todo',
        'afazer': 'todo',
        'to do': 'todo',
        'in-progress': 'in-progress',
        'in progress': 'in-progress',
        'em progresso': 'in-progress',
        'progress': 'in-progress',
        'done': 'done',
        'concluido': 'done',
        'concluído': 'done',
        'finalizado': 'done',
    }
    return aliases.get(value, 'todo')


def _normalize_kanban_priority(value: str) -> str:
    value = (value or '').strip().lower()
    aliases = {
        'high': 'high',
        'alta': 'high',
        'medium': 'medium',
        'media': 'medium',
        'média': 'medium',
        'low': 'low',
        'baixa': 'low',
    }
    return aliases.get(value, 'medium')


def _extract_openrouter_text(payload: dict) -> str:
    choices = payload.get('choices') or []
    if not choices:
        raise ValueError('A IA não retornou conteúdo')
    message = choices[0].get('message') or {}
    content = message.get('content')
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                parts.append(item.get('text', ''))
        content = ''.join(parts)
    content = (content or '').strip()
    if not content:
        raise ValueError('A IA retornou conteúdo vazio')
    return content


def _extract_json_block(text: str):
    text = (text or '').strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return json.loads(match.group(1))
    start_obj = text.find('{')
    end_obj = text.rfind('}')
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        snippet = text[start_obj:end_obj + 1]
        try:
            return json.loads(snippet)
        except Exception:
            pass
    start_arr = text.find('[')
    end_arr = text.rfind(']')
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        snippet = text[start_arr:end_arr + 1]
        return json.loads(snippet)
    raise ValueError('A IA retornou um formato inválido')


def _sanitize_kanban_task_payload(task: dict) -> dict:
    return {
        'title': (task.get('title') or '').strip(),
        'description': (task.get('description') or '').strip(),
        'status': _normalize_kanban_status(task.get('status') or 'todo'),
        'priority': _normalize_kanban_priority(task.get('priority') or 'medium'),
    }


def _sanitize_kanban_plan_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    base_task = _sanitize_kanban_task_payload(payload.get('task') or {})
    base_task['categoria'] = ((payload.get('task') or {}).get('categoria') or '').strip().upper()
    base_task['data_vencimento'] = ((payload.get('task') or {}).get('data_vencimento') or '').strip()
    base_task['responsavel'] = ((payload.get('task') or {}).get('responsavel') or '').strip()

    subtarefas = []
    for item in payload.get('subtarefas') or []:
        if not isinstance(item, dict):
            continue
        task_item = _sanitize_kanban_task_payload(item)
        if task_item['title']:
            subtarefas.append(task_item)

    checklist = []
    for item in payload.get('checklist') or []:
        text = str(item or '').strip()
        if text:
            checklist.append(text)

    next_action = str(payload.get('next_action') or '').strip()
    resumo = str(payload.get('summary') or '').strip()

    return {
        'task': base_task,
        'summary': resumo,
        'next_action': next_action,
        'checklist': checklist[:8],
        'subtarefas': subtarefas[:6],
    }


def _sanitize_kanban_task_classification_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    categoria = str(payload.get('categoria_ia') or payload.get('categoria') or '').strip().lower()
    if categoria not in {'financeiro', 'documento', 'prazo', 'auditoria', 'protocolo'}:
        categoria = 'documento'
    justificativa = str(payload.get('justificativa') or '').strip()
    confianca_raw = payload.get('confianca', 0)
    try:
        confianca = float(confianca_raw)
    except Exception:
        confianca = 0.0
    return {
        'categoria_ia': categoria,
        'justificativa': justificativa,
        'confianca': max(0.0, min(1.0, confianca)),
    }


def _sanitize_kanban_stale_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    status = str(payload.get('status') or 'normal').strip().lower()
    if status not in {'normal', 'atencao', 'parada'}:
        status = 'normal'
    dias = payload.get('dias_sem_atualizacao', 0)
    try:
        dias = int(dias)
    except Exception:
        dias = 0
    sugestoes = []
    for item in payload.get('sugestoes') or []:
        text = str(item or '').strip()
        if text:
            sugestoes.append(text)
    return {
        'status': status,
        'dias_sem_atualizacao': max(0, dias),
        'resumo': str(payload.get('resumo') or '').strip(),
        'sugestoes': sugestoes[:4],
    }


def _kanban_ai_completion(action: str, user_prompt: str, task: dict | None = None, api_key_override: str = '', model_override: str = '', status_hint: str = '', priority_hint: str = ''):
    from blueprints.ia import _get_openrouter_config, _build_ai_service
    conn = get_db()
    api_key, model = _get_openrouter_config(conn, api_key_override=api_key_override, model_override=model_override)
    if not api_key:
        return None, ('A IA do Kanban não encontrou a chave do OpenRouter. Salve a mesma chave usada nas outras abas em Configurações.', 400)

    today = __import__('datetime').date.today().strftime('%d/%m/%Y')

    hints_create = ''
    if status_hint:
        hints_create += f' O status deve ser "{status_hint}".'
    if priority_hint:
        hints_create += f' A prioridade deve ser "{priority_hint}".'

    system_map = {
        'create': (
            f'Você é um assistente especializado em Kanban para a Prefeitura Municipal de Inajá. '
            f'Hoje é {today}. '
            'Com base na descrição do usuário, crie uma tarefa bem estruturada. '
            'Responda APENAS com JSON válido contendo as chaves: '
            '"title" (título objetivo e claro, máx 80 chars), '
            '"description" (descrição detalhada com contexto, passos ou informações relevantes), '
            '"status" (um de: todo, in-progress, done), '
            '"priority" (um de: low, medium, high). '
            'O título deve ser conciso e direto. A descrição deve ser útil e informativa. '
            f'{hints_create} '
            'Escreva em português do Brasil. Não inclua texto fora do JSON.'
        ),
        'improve': (
            f'Você é um assistente especializado em Kanban para a Prefeitura Municipal de Inajá. '
            f'Hoje é {today}. '
            'Melhore a tarefa recebida conforme o pedido do usuário. '
            'Responda APENAS com JSON válido contendo as chaves: '
            '"title" (título melhorado, objetivo e claro, máx 80 chars), '
            '"description" (descrição aprimorada, detalhada e útil), '
            '"status" (um de: todo, in-progress, done), '
            '"priority" (um de: low, medium, high). '
            'Preserve o status atual a menos que o usuário peça para mudar. '
            'Escreva em português do Brasil. Não inclua texto fora do JSON.'
        ),
        'breakdown': (
            f'Você é um assistente especializado em Kanban para a Prefeitura Municipal de Inajá. '
            f'Hoje é {today}. '
            'Quebre a tarefa recebida em subtarefas práticas e acionáveis. '
            'Responda APENAS com JSON válido no formato: '
            '{"tasks":[{"title":"","description":"","status":"todo","priority":"medium"},...]}. '
            'Gere entre 3 e 7 subtarefas. Cada subtarefa deve ter: '
            '"title" (objetivo e claro, máx 80 chars), '
            '"description" (passos ou detalhes práticos), '
            '"status" (sempre "todo" para novas subtarefas), '
            '"priority" (um de: low, medium, high — atribua conforme urgência). '
            'As subtarefas devem ser ordenadas logicamente (do primeiro ao último passo). '
            'Escreva em português do Brasil. Não inclua texto fora do JSON.'
        ),
        'plan': (
            f'Você é um assistente especializado em Kanban para a Prefeitura Municipal de Inajá. '
            f'Hoje é {today}. '
            'Analise a tarefa recebida e gere um plano de ação prático para execução administrativa. '
            'Responda APENAS com JSON válido no formato: '
            '{"task":{"title":"","description":"","status":"todo","priority":"medium"},'
            '"summary":"","next_action":"","checklist":[""],'
            '"subtarefas":[{"title":"","description":"","status":"todo","priority":"medium"}]}. '
            'Reescreva a tarefa principal de forma mais clara, profissional e objetiva. '
            'Em "summary", traga um resumo executivo curto com no máximo 220 caracteres. '
            'Em "next_action", informe a próxima ação mais recomendada em uma frase curta. '
            'Em "checklist", gere de 3 a 8 itens curtos e verificáveis. '
            'Em "subtarefas", gere de 2 a 6 passos práticos e ordenados logicamente. '
            'Ajuste a prioridade para low, medium ou high conforme urgência e impacto. '
            'Preserve o status atual, a menos que haja motivo claro para mudar para "done". '
            'Escreva em português do Brasil. Não inclua texto fora do JSON.'
        ),
        'classify': (
            f'Você é um assistente especializado em classificação de tarefas administrativas da Prefeitura Municipal de Inajá. '
            f'Hoje é {today}. '
            'Analise a tarefa recebida e classifique seu tipo principal. '
            'Responda APENAS com JSON válido no formato: '
            '{"categoria_ia":"financeiro|documento|prazo|auditoria|protocolo","confianca":0.0,"justificativa":""}. '
            'Escolha apenas uma categoria principal. '
            'A justificativa deve ser curta, objetiva e administrativa. '
            'Não inclua texto fora do JSON.'
        ),
        'stale': (
            f'Você é um assistente especializado em gestão de tarefas administrativas da Prefeitura Municipal de Inajá. '
            f'Hoje é {today}. '
            'Analise se a tarefa está parada ou sem atualização há tempo demais e sugira ações administrativas. '
            'Responda APENAS com JSON válido no formato: '
            '{"status":"normal|atencao|parada","dias_sem_atualizacao":0,"resumo":"","sugestoes":[""]}. '
            'Em "status", use "normal", "atencao" ou "parada". '
            'Em "resumo", descreva a situação em uma frase curta. '
            'Em "sugestoes", inclua até 4 ações curtas dentre ideias como cobrar responsável, arquivar, redefinir prazo ou mover de coluna. '
            'Não inclua texto fora do JSON.'
        ),
        'professional_rewrite': (
            f'Você é um redator técnico da administração pública municipal. '
            f'Hoje é {today}. '
            'Reescreva a tarefa para ficar mais objetiva, clara e profissional, mantendo fidelidade ao conteúdo. '
            'Responda APENAS com JSON válido contendo as chaves: '
            '"title", "description", "status", "priority". '
            'O texto deve soar administrativo, direto e bem organizado. '
            'Preserve o status atual. Ajuste a prioridade apenas se houver motivo claro. '
            'Não inclua texto fora do JSON.'
        ),
    }
    messages = [{'role': 'system', 'content': system_map[action]}]
    if task:
        messages.append({
            'role': 'user',
            'content': (
                f'Tarefa atual:\n{json.dumps(task, ensure_ascii=False)}\n\n'
                f'Pedido do usuário:\n{user_prompt or "Melhore esta tarefa."}'
            )
        })
    else:
        messages.append({'role': 'user', 'content': user_prompt})
    try:
        response = _build_ai_service(api_key, model).chat_by_task(
            task_type='chat',
            messages=messages,
            temperature=0.4,
            max_tokens=900,
            use_cache=False,
            metadata={'feature': 'kanban_ai', 'action': action},
        )
        return _extract_json_block(response.text), None
    except AIServiceError as err:
        return None, (err.user_message, err.status_code)
    except Exception as err:
        current_app.logger.error('_kanban_ai_completion error (action=%s): %s', action, err)
        return None, (str(err), 500)


@bp.route('/kanban', methods=['GET'])
def kanban_listar():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT id, title, description, status, priority, categoria, data_vencimento, responsavel, concluido_em, criado_em, atualizado_em FROM kanban_tasks ORDER BY atualizado_em DESC, criado_em DESC"
        ).fetchall()
        tasks = [row_to_dict(r) for r in rows]
        attach_rows = conn.execute(
            "SELECT id, task_id, file_name, mime_type, file_size, criado_em FROM kanban_attachments ORDER BY criado_em DESC, id DESC"
        ).fetchall()
        attachments_by_task: dict[str, list[dict]] = defaultdict(list)
        for row in attach_rows:
            payload = row_to_dict(row)
            attachments_by_task[payload['task_id']].append(payload)
        for task in tasks:
            task['attachments'] = attachments_by_task.get(task['id'], [])
        return jsonify(tasks)
    except Exception as e:
        current_app.logger.error('GET /api/kanban: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban', methods=['POST'])
def kanban_criar():
    try:
        data = request.get_json(force=True) or {}
        task_id = (data.get('id') or '').strip()
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        status = (data.get('status') or 'todo').strip()
        priority = (data.get('priority') or 'medium').strip()
        categoria = (data.get('categoria') or '').strip().upper()
        data_vencimento = (data.get('data_vencimento') or '').strip()
        responsavel = (data.get('responsavel') or '').strip()
        concluido_em = ''
        if not task_id:
            return jsonify({'error': 'id é obrigatório'}), 400
        if not title:
            return jsonify({'error': 'title é obrigatório'}), 400
        if status not in {'todo', 'in-progress', 'done'}:
            status = 'todo'
        if priority not in {'low', 'medium', 'high'}:
            priority = 'medium'
        if status == 'done':
            concluido_em = _time.strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db()
        conn.execute(
            "INSERT INTO kanban_tasks (id, title, description, status, priority, categoria, data_vencimento, responsavel, concluido_em, criado_em, atualizado_em) VALUES (?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))",
            (task_id, title, description, status, priority, categoria, data_vencimento, responsavel, concluido_em)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, title, description, status, priority, categoria, data_vencimento, responsavel, concluido_em, criado_em, atualizado_em FROM kanban_tasks WHERE id=?",
            (task_id,)
        ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Já existe uma tarefa com esse id'}), 409
    except Exception as e:
        current_app.logger.error('POST /api/kanban: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>', methods=['PUT'])
def kanban_atualizar(task_id):
    try:
        data = request.get_json(force=True) or {}
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        status = (data.get('status') or 'todo').strip()
        priority = (data.get('priority') or 'medium').strip()
        categoria = (data.get('categoria') or '').strip().upper()
        data_vencimento = (data.get('data_vencimento') or '').strip()
        responsavel = (data.get('responsavel') or '').strip()
        if not title:
            return jsonify({'error': 'title é obrigatório'}), 400
        if status not in {'todo', 'in-progress', 'done'}:
            status = 'todo'
        if priority not in {'low', 'medium', 'high'}:
            priority = 'medium'
        conn = get_db()
        current = conn.execute("SELECT status, concluido_em FROM kanban_tasks WHERE id=?", (task_id,)).fetchone()
        if not current:
            return jsonify({'error': 'Tarefa não encontrada'}), 404
        concluido_em = current['concluido_em'] or ''
        if status == 'done' and current['status'] != 'done':
            concluido_em = _time.strftime('%Y-%m-%d %H:%M:%S')
        elif status != 'done':
            concluido_em = ''
        cur = conn.execute(
            "UPDATE kanban_tasks SET title=?, description=?, status=?, priority=?, categoria=?, data_vencimento=?, responsavel=?, concluido_em=?, atualizado_em=datetime('now','localtime') WHERE id=?",
            (title, description, status, priority, categoria, data_vencimento, responsavel, concluido_em, task_id)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, title, description, status, priority, categoria, data_vencimento, responsavel, concluido_em, criado_em, atualizado_em FROM kanban_tasks WHERE id=?",
            (task_id,)
        ).fetchone()
        return jsonify(row_to_dict(row))
    except Exception as e:
        current_app.logger.error('PUT /api/kanban/%s: %s', task_id, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>', methods=['DELETE'])
def kanban_excluir(task_id):
    try:
        conn = get_db()
        cur = conn.execute("DELETE FROM kanban_tasks WHERE id=?", (task_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Tarefa não encontrada'}), 404
        return jsonify({'ok': True})
    except Exception as e:
        current_app.logger.error('DELETE /api/kanban/%s: %s', task_id, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/ai/create-from-text', methods=['POST'])
def kanban_ai_create_from_text():
    try:
        data = request.get_json(force=True) or {}
        prompt = (data.get('prompt') or '').strip()
        if not prompt:
            return jsonify({'error': 'Informe o texto para a IA gerar a tarefa'}), 400
        parsed, error = _kanban_ai_completion(
            'create',
            prompt,
            api_key_override=(data.get('api_key') or '').strip(),
            model_override=(data.get('model') or '').strip(),
            status_hint=(data.get('status_hint') or '').strip(),
            priority_hint=(data.get('priority_hint') or '').strip()
        )
        if error:
            return jsonify({'error': error[0]}), error[1]
        task = _sanitize_kanban_task_payload(parsed if isinstance(parsed, dict) else {})
        if not task['title']:
            return jsonify({'error': 'A IA não retornou um título válido para a tarefa'}), 502
        return jsonify(task)
    except Exception as e:
        current_app.logger.error('POST /api/kanban/ai/create-from-text: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/ai/improve-task', methods=['POST'])
def kanban_ai_improve_task():
    try:
        data = request.get_json(force=True) or {}
        task = data.get('task') or {}
        prompt = (data.get('prompt') or '').strip()
        if not isinstance(task, dict) or not (task.get('title') or '').strip():
            return jsonify({'error': 'Envie uma tarefa válida para a IA melhorar'}), 400
        current_task = _sanitize_kanban_task_payload(task)
        current_task['title'] = (task.get('title') or '').strip()
        parsed, error = _kanban_ai_completion(
            'improve',
            prompt,
            current_task,
            api_key_override=(data.get('api_key') or '').strip(),
            model_override=(data.get('model') or '').strip()
        )
        if error:
            return jsonify({'error': error[0]}), error[1]
        improved = _sanitize_kanban_task_payload(parsed if isinstance(parsed, dict) else {})
        if not improved['title']:
            return jsonify({'error': 'A IA não retornou um título válido'}), 502
        return jsonify(improved)
    except Exception as e:
        current_app.logger.error('POST /api/kanban/ai/improve-task: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/ai/breakdown-task', methods=['POST'])
def kanban_ai_breakdown_task():
    try:
        data = request.get_json(force=True) or {}
        task = data.get('task') or {}
        prompt = (data.get('prompt') or '').strip()
        if not isinstance(task, dict) or not (task.get('title') or '').strip():
            return jsonify({'error': 'Envie uma tarefa válida para a IA quebrar em subtarefas'}), 400
        current_task = _sanitize_kanban_task_payload(task)
        current_task['title'] = (task.get('title') or '').strip()
        parsed, error = _kanban_ai_completion(
            'breakdown',
            prompt,
            current_task,
            api_key_override=(data.get('api_key') or '').strip(),
            model_override=(data.get('model') or '').strip()
        )
        if error:
            return jsonify({'error': error[0]}), error[1]
        items = parsed.get('tasks') if isinstance(parsed, dict) else parsed
        if not isinstance(items, list):
            return jsonify({'error': 'A IA não retornou uma lista válida de subtarefas'}), 502
        tasks = []
        for item in items:
            if not isinstance(item, dict):
                continue
            task_payload = _sanitize_kanban_task_payload(item)
            if task_payload['title']:
                tasks.append(task_payload)
        if not tasks:
            return jsonify({'error': 'A IA não gerou subtarefas válidas'}), 502
        return jsonify({'tasks': tasks})
    except Exception as e:
        current_app.logger.error('POST /api/kanban/ai/breakdown-task: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/ai/plan-task', methods=['POST'])
def kanban_ai_plan_task():
    try:
        data = request.get_json(force=True) or {}
        task = data.get('task') or {}
        prompt = (data.get('prompt') or '').strip()
        if not isinstance(task, dict) or not (task.get('title') or '').strip():
            return jsonify({'error': 'Envie uma tarefa válida para a IA planejar'}), 400
        current_task = {
            **_sanitize_kanban_task_payload(task),
            'title': (task.get('title') or '').strip(),
            'categoria': (task.get('categoria') or '').strip().upper(),
            'data_vencimento': (task.get('data_vencimento') or '').strip(),
            'responsavel': (task.get('responsavel') or '').strip(),
        }
        parsed, error = _kanban_ai_completion(
            'plan',
            prompt,
            current_task,
            api_key_override=(data.get('api_key') or '').strip(),
            model_override=(data.get('model') or '').strip()
        )
        if error:
            return jsonify({'error': error[0]}), error[1]
        plan = _sanitize_kanban_plan_payload(parsed if isinstance(parsed, dict) else {})
        if not plan['task']['title']:
            return jsonify({'error': 'A IA não retornou uma tarefa principal válida'}), 502
        if not plan['checklist']:
            return jsonify({'error': 'A IA não retornou checklist válido para o planejamento'}), 502
        return jsonify(plan)
    except Exception as e:
        current_app.logger.error('POST /api/kanban/ai/plan-task: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/ai/classify-task', methods=['POST'])
def kanban_ai_classify_task():
    try:
        data = request.get_json(force=True) or {}
        task = data.get('task') or {}
        prompt = (data.get('prompt') or '').strip()
        if not isinstance(task, dict) or not (task.get('title') or '').strip():
            return jsonify({'error': 'Envie uma tarefa válida para a IA classificar'}), 400
        current_task = {
            **_sanitize_kanban_task_payload(task),
            'title': (task.get('title') or '').strip(),
            'categoria': (task.get('categoria') or '').strip().upper(),
            'data_vencimento': (task.get('data_vencimento') or '').strip(),
            'responsavel': (task.get('responsavel') or '').strip(),
        }
        parsed, error = _kanban_ai_completion(
            'classify',
            prompt or 'Classifique o tipo principal desta tarefa.',
            current_task,
            api_key_override=(data.get('api_key') or '').strip(),
            model_override=(data.get('model') or '').strip()
        )
        if error:
            return jsonify({'error': error[0]}), error[1]
        result = _sanitize_kanban_task_classification_payload(parsed if isinstance(parsed, dict) else {})
        return jsonify(result)
    except Exception as e:
        current_app.logger.error('POST /api/kanban/ai/classify-task: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/ai/stale-task', methods=['POST'])
def kanban_ai_stale_task():
    try:
        data = request.get_json(force=True) or {}
        task = data.get('task') or {}
        prompt = (data.get('prompt') or '').strip()
        if not isinstance(task, dict) or not (task.get('title') or '').strip():
            return jsonify({'error': 'Envie uma tarefa válida para analisar parada'}), 400
        current_task = {
            **_sanitize_kanban_task_payload(task),
            'title': (task.get('title') or '').strip(),
            'categoria': (task.get('categoria') or '').strip().upper(),
            'data_vencimento': (task.get('data_vencimento') or '').strip(),
            'responsavel': (task.get('responsavel') or '').strip(),
            'criado_em': (task.get('criado_em') or '').strip(),
            'atualizado_em': (task.get('atualizado_em') or '').strip(),
        }
        parsed, error = _kanban_ai_completion(
            'stale',
            prompt or 'Avalie se a tarefa está parada e sugira ações.',
            current_task,
            api_key_override=(data.get('api_key') or '').strip(),
            model_override=(data.get('model') or '').strip()
        )
        if error:
            return jsonify({'error': error[0]}), error[1]
        result = _sanitize_kanban_stale_payload(parsed if isinstance(parsed, dict) else {})
        return jsonify(result)
    except Exception as e:
        current_app.logger.error('POST /api/kanban/ai/stale-task: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/ai/professional-rewrite', methods=['POST'])
def kanban_ai_professional_rewrite():
    try:
        data = request.get_json(force=True) or {}
        task = data.get('task') or {}
        prompt = (data.get('prompt') or '').strip()
        if not isinstance(task, dict) or not (task.get('title') or '').strip():
            return jsonify({'error': 'Envie uma tarefa válida para reescrita profissional'}), 400
        current_task = _sanitize_kanban_task_payload(task)
        current_task['title'] = (task.get('title') or '').strip()
        parsed, error = _kanban_ai_completion(
            'professional_rewrite',
            prompt or 'Reescreva a tarefa em tom profissional e administrativo.',
            current_task,
            api_key_override=(data.get('api_key') or '').strip(),
            model_override=(data.get('model') or '').strip()
        )
        if error:
            return jsonify({'error': error[0]}), error[1]
        rewritten = _sanitize_kanban_task_payload(parsed if isinstance(parsed, dict) else {})
        if not rewritten['title']:
            return jsonify({'error': 'A IA não retornou um título válido para a reescrita'}), 502
        return jsonify(rewritten)
    except Exception as e:
        current_app.logger.error('POST /api/kanban/ai/professional-rewrite: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>/attachments', methods=['GET'])
def kanban_anexos_listar(task_id):
    try:
        conn = get_db()
        task = conn.execute("SELECT id FROM kanban_tasks WHERE id=?", (task_id,)).fetchone()
        if not task:
            return jsonify({'error': 'Tarefa não encontrada'}), 404
        rows = conn.execute(
            "SELECT id, task_id, file_name, mime_type, file_size, criado_em FROM kanban_attachments WHERE task_id=? ORDER BY criado_em DESC, id DESC",
            (task_id,)
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        current_app.logger.error('GET /api/kanban/%s/attachments: %s', task_id, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>/attachments', methods=['POST'])
def kanban_anexos_enviar(task_id):
    file = request.files.get('arquivo')
    if not file or not file.filename:
        return jsonify({'error': 'Arquivo é obrigatório'}), 400
    try:
        content = file.read()
        if not content:
            return jsonify({'error': 'Arquivo vazio'}), 400
        if len(content) > 10 * 1024 * 1024:
            return jsonify({'error': 'Arquivo excede o limite de 10 MB'}), 413
        conn = get_db()
        task = conn.execute(
            "SELECT id, title FROM kanban_tasks WHERE id=?",
            (task_id,)
        ).fetchone()
        if not task:
            return jsonify({'error': 'Tarefa não encontrada'}), 404
        cur = conn.execute(
            "INSERT INTO kanban_attachments (task_id, file_name, mime_type, file_size, content, criado_em) VALUES (?,?,?,?,?,datetime('now','localtime'))",
            (task_id, file.filename, file.mimetype or 'application/octet-stream', len(content), content)
        )
        attachment_id = cur.lastrowid
        conn.commit()
        row = conn.execute(
            "SELECT id, task_id, file_name, mime_type, file_size, criado_em FROM kanban_attachments WHERE id=?",
            (attachment_id,)
        ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        current_app.logger.error('POST /api/kanban/%s/attachments: %s', task_id, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>/attachments/<int:attachment_id>/download', methods=['GET'])
def kanban_anexo_download(task_id, attachment_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT id, task_id, file_name, mime_type, content FROM kanban_attachments WHERE id=? AND task_id=?",
            (attachment_id, task_id)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Anexo não encontrado'}), 404
        return send_file(
            _io.BytesIO(row['content']),
            mimetype=row['mime_type'] or 'application/octet-stream',
            as_attachment=True,
            download_name=row['file_name']
        )
    except Exception as e:
        current_app.logger.error('GET /api/kanban/%s/attachments/%s/download: %s', task_id, attachment_id, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>/attachments/<int:attachment_id>', methods=['DELETE'])
def kanban_anexo_excluir(task_id, attachment_id):
    try:
        conn = get_db()
        cur = conn.execute(
            "DELETE FROM kanban_attachments WHERE id=? AND task_id=?",
            (attachment_id, task_id)
        )
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Anexo não encontrado'}), 404
        return jsonify({'ok': True})
    except Exception as e:
        current_app.logger.error('DELETE /api/kanban/%s/attachments/%s: %s', task_id, attachment_id, e)
        return jsonify({'error': str(e)}), 500
