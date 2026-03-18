import os

from flask import Blueprint, request, jsonify, current_app
from config import settings
from database import get_db, row_to_dict
from services.openrouter_service import AIServiceError, build_openrouter_service, listar_modelos
from services.ai_tasks import AITaskFacade

bp = Blueprint('ia', __name__)


def _get_openrouter_config(conn, api_key_override: str = '', model_override: str = ''):
    rows = conn.execute(
        "SELECT chave, valor FROM configuracoes WHERE chave IN (?, ?)",
        ('api_openrouter_key', 'api_openrouter_modelo')
    ).fetchall()
    cfg = {row['chave']: (row['valor'] or '').strip() for row in rows}
    env_api_key = (os.environ.get('OPENROUTER_API_KEY') or '').strip()
    env_model = (os.environ.get('OPENROUTER_MODEL') or '').strip()
    api_key = (api_key_override or '').strip() or cfg.get('api_openrouter_key', '') or env_api_key
    raw_model = (model_override or '').strip() or cfg.get('api_openrouter_modelo', '') or env_model or settings.openrouter_default_model
    model = _normalize_openrouter_free_model(raw_model)
    return api_key, model


def _normalize_openrouter_free_model(model: str) -> str:
    normalized = (model or '').strip()
    if not normalized:
        return 'openrouter/free'
    if normalized == 'openrouter/free' or normalized.endswith(':free'):
        return normalized
    return 'openrouter/free'


def _build_ai_service(api_key: str, model: str):
    return build_openrouter_service(
        api_key=api_key,
        default_model=model or settings.openrouter_default_model,
        referer=settings.openrouter_referer,
        title=settings.openrouter_title,
        logger=current_app.logger,
        timeout_seconds=settings.openrouter_timeout_seconds,
        max_retries=settings.openrouter_max_retries,
        backoff_base=settings.openrouter_backoff_base,
        cache_ttl_seconds=settings.openrouter_cache_ttl_seconds,
    )


def _build_ai_facade(api_key: str, model: str):
    return AITaskFacade(_build_ai_service(api_key, model))


@bp.route('/extratos/modelos-openrouter', methods=['GET', 'POST'])
def extratos_modelos_openrouter():
    try:
        data = request.get_json(silent=True) or {}
        conn = get_db()
        api_key, selected_model = _get_openrouter_config(
            conn,
            api_key_override=(data.get('api_key') or request.args.get('api_key') or '').strip(),
            model_override=(data.get('model') or request.args.get('model') or '').strip()
        )
        if not api_key:
            return jsonify({
                'error': 'Nenhuma chave do OpenRouter foi encontrada. Use a mesma chave já configurada nas outras abas.',
                'modelos': [],
                'models': [],
                'selected_model': selected_model,
            }), 400
        models = listar_modelos(
            api_key,
            timeout_seconds=settings.openrouter_timeout_seconds,
            referer=settings.openrouter_referer,
            title=settings.openrouter_title,
        )
        normalized = []
        for model in models:
            if not isinstance(model, dict):
                continue
            pricing = model.get('pricing') or {}
            prompt_price = str(pricing.get('prompt') or '').strip()
            completion_price = str(pricing.get('completion') or '').strip()
            if prompt_price != '0' or completion_price != '0':
                continue
            normalized.append({
                'id': (model.get('id') or '').strip(),
                'name': (model.get('name') or model.get('id') or '').strip(),
                'context_length': model.get('context_length'),
                'pricing': pricing,
            })
        return jsonify({
            'modelos': normalized,
            'models': normalized,
            'selected_model': selected_model,
        })
    except AIServiceError as err:
        return jsonify({'error': err.user_message, 'modelos': [], 'models': []}), err.status_code
    except Exception as e:
        current_app.logger.error('%s /api/extratos/modelos-openrouter: %s', request.method, e)
        return jsonify({'error': str(e), 'modelos': [], 'models': []}), 500


@bp.route('/ia/chat', methods=['POST'])
def proxy_ia_chat():
    try:
        data = request.get_json(force=True) or {}
        conn = get_db()
        api_key, model = _get_openrouter_config(
            conn,
            api_key_override=(data.get('api_key') or '').strip(),
            model_override=(data.get('model') or '').strip()
        )
        if not api_key:
            return jsonify({'error': 'Chave API OpenRouter não configurada. Configure na aba ADM.'}), 400

        messages = data.get('messages', [])
        temperature = data.get('temperature', 0.2)
        max_tokens = data.get('max_tokens', 2000)

        response = _build_ai_service(api_key, model).chat_by_task(
            task_type='chat',
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            use_cache=bool(data.get('use_cache', False)),
            response_format=data.get('response_format'),
            stream=bool(data.get('stream', False)),
            metadata={'feature': 'proxy_ia_chat'},
        )
        return jsonify(response.payload)
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as e:
        current_app.logger.error('POST /api/ia/chat: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/empenho-assistente', methods=['POST'])
def empenho_assistente():
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip()
    payload = data.get('payload') or {}

    conn = get_db()
    api_key, model = _get_openrouter_config(conn)
    if not api_key:
        return jsonify({'error': 'Chave do OpenRouter não configurada. Acesse ADM -> Configuracoes -> Chaves de API.'}), 400
    if action not in {'extract_fields', 'generate_description', 'checklist', 'improve_description'}:
        return jsonify({'error': 'Acao invalida. Use: extract_fields, generate_description, checklist, improve_description.'}), 400
    try:
        facade = _build_ai_facade(api_key, model)
        result = facade.gerar_texto_empenho(payload, acao=action)
        if isinstance(result, dict):
            return jsonify({'action': action, 'resultado': result})
        return jsonify({
            'action': action,
            'resultado': result.content,
            'meta': {
                'model': result.model,
                'cached': result.cached,
                'usage': result.usage,
            }
        })
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as err:
        current_app.logger.error('POST /api/empenho-assistente: %s', err)
        return jsonify({'error': str(err)}), 500
