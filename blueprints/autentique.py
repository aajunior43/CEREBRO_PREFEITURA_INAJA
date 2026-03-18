import os
import re
import json
import mimetypes
import requests

from flask import Blueprint, request, jsonify, send_file, current_app
from database import get_db, row_to_dict, DOCUMENTS_DIR
from blueprints.documentos import _persist_document_file

bp = Blueprint('autentique', __name__)


def _parse_autentique_keys(value: str) -> list[str]:
    text = (value or '').replace('\r', '\n')
    raw_items = []
    for chunk in text.split('\n'):
        raw_items.extend(part.strip() for part in chunk.split(','))
    keys = [item for item in raw_items if item]
    seen = set()
    unique = []
    for item in keys:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _get_autentique_config(conn, api_key_override: str = ''):
    rows = conn.execute(
        "SELECT chave, valor FROM configuracoes WHERE chave IN (?, ?)",
        ('api_autentique_key', 'api_autentique_key_cursor')
    ).fetchall()
    cfg = {row['chave']: (row['valor'] or '').strip() for row in rows}
    override_keys = _parse_autentique_keys(api_key_override)
    if override_keys:
        return override_keys[0]

    configured_keys = _parse_autentique_keys(cfg.get('api_autentique_key', ''))
    env_keys = _parse_autentique_keys(os.environ.get('AUTENTIQUE_API_KEY') or '')
    keys = configured_keys or env_keys
    if not keys:
        return ''

    if len(keys) == 1:
        return keys[0]

    try:
        cursor = int(cfg.get('api_autentique_key_cursor', '0') or '0')
    except ValueError:
        cursor = 0
    index = cursor % len(keys)
    selected = keys[index]
    try:
        conn.execute(
            "INSERT INTO configuracoes (chave, valor, atualizado_em) VALUES (?,?,datetime('now','localtime')) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor, atualizado_em=excluded.atualizado_em",
            ('api_autentique_key_cursor', str((index + 1) % len(keys)))
        )
        conn.commit()
    except Exception:
        pass
    return selected


def _normalize_phone_br(value: str) -> str:
    digits = re.sub(r'\D+', '', value or '')
    if digits.startswith('55') and len(digits) >= 12:
        return '+' + digits
    if len(digits) in {10, 11}:
        return '+55' + digits
    return ('+' + digits) if digits else ''


def _autentique_guess_status(*values) -> str:
    text = ' '.join(str(v or '').strip().lower() for v in values if v)
    if any(token in text for token in ('signed', 'assinado', 'completed', 'complete', 'finalizado', 'finished', 'concluido')):
        return 'assinado'
    if any(token in text for token in ('rejected', 'recusado', 'declined')):
        return 'recusado'
    if any(token in text for token in ('canceled', 'cancelado', 'cancelled')):
        return 'cancelado'
    if any(token in text for token in ('expired', 'expirado')):
        return 'expirado'
    return 'pendente'


def _autentique_scan_payload(node, trail=''):
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            path = f'{trail}.{key}' if trail else str(key)
            found.extend(_autentique_scan_payload(value, path))
            if isinstance(value, (str, int, float, bool)) or value is None:
                found.append((path.lower(), value))
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            path = f'{trail}[{idx}]' if trail else f'[{idx}]'
            found.extend(_autentique_scan_payload(value, path))
    return found


def _autentique_extract_webhook(payload: dict) -> dict:
    entries = _autentique_scan_payload(payload)
    event_name = ''
    document_id = ''
    signature_public_id = ''
    signature_link = ''
    download_url = ''
    signed_at = ''
    delivery_method = ''
    status_values = []

    for path, value in entries:
        text = '' if value is None else str(value).strip()
        if not text:
            continue
        lower = text.lower()
        if not event_name and path.endswith(('event', 'type', 'action', 'name')) and any(token in lower for token in ('sign', 'document', 'signature', 'webhook')):
            event_name = text
        if not document_id and any(token in path for token in ('document.id', 'document_id', 'createDocument.id', 'document.public_id')):
            document_id = text
        if not signature_public_id and ('public_id' in path or 'signature_id' in path):
            signature_public_id = text
        if not signature_link and 'link.short_link' in path:
            signature_link = text
        if not signed_at and any(token in path for token in ('signed_at', 'completed_at', 'finished_at')):
            signed_at = text
        if not delivery_method and 'delivery_method' in path:
            delivery_method = text
        if ('status' in path) or path.endswith(('event', 'type', 'action')):
            status_values.append(text)
        if text.startswith('http'):
            key_hint = path.split('.')[-1]
            if not download_url and any(token in key_hint for token in ('download', 'signed', 'file_url', 'original_file', 'arquivo')):
                download_url = text

    status = _autentique_guess_status(event_name, signed_at, *status_values)
    return {
        'event_name': event_name,
        'document_id': document_id,
        'signature_public_id': signature_public_id,
        'signature_link': signature_link,
        'download_url': download_url,
        'signed_at': signed_at,
        'delivery_method': delivery_method or 'DELIVERY_METHOD_WHATSAPP',
        'status': status,
    }


def _autentique_save_signed_document(download_url: str, original_name: str, api_key: str):
    if not download_url:
        return None
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
    resp = requests.get(download_url, headers=headers, timeout=90)
    if resp.status_code >= 400:
        resp = requests.get(download_url, timeout=90)
    resp.raise_for_status()
    signed_name_root, _ = os.path.splitext(original_name or 'documento')
    signed_name = f'{signed_name_root}-assinado.pdf'
    saved = _persist_document_file(
        signed_name,
        resp.content,
        'assinados_autentique',
        'assinatura-digital',
        'Documento assinado recebido pela integração da Autentique',
        resp.headers.get('Content-Type') or 'application/pdf'
    )
    return saved


@bp.route('/autentique/testar', methods=['POST'])
def autentique_testar():
    data = request.get_json(silent=True) or {}
    try:
        conn = get_db()
        api_key = _get_autentique_config(conn, api_key_override=(data.get('api_key') or '').strip())
        if not api_key:
            return jsonify({'error': 'Chave da Autentique não configurada. Acesse ADM -> Chaves de API.'}), 400

        query = {
            'query': 'query { me { id name email } }'
        }
        resp = requests.post(
            'https://api.autentique.com.br/v2/graphql',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json=query,
            timeout=35,
        )
        payload = resp.json()
        if resp.status_code >= 400 or payload.get('errors'):
            message = (payload.get('errors') or [{}])[0].get('message') or f'Erro HTTP {resp.status_code}'
            return jsonify({'error': message}), resp.status_code or 502
        user = ((payload.get('data') or {}).get('me') or {})
        return jsonify({'ok': True, 'usuario': user})
    except requests.RequestException as err:
        return jsonify({'error': f'Falha de conexão com a Autentique: {err}'}), 502
    except Exception as err:
        current_app.logger.error('POST /api/autentique/testar: %s', err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/saldo', methods=['GET'])
def autentique_saldo():
    try:
        conn = get_db()
        api_key = _get_autentique_config(conn, api_key_override=(request.args.get('api_key') or '').strip())
        if not api_key:
            return jsonify({'error': 'Chave da Autentique não configurada. Acesse ADM -> Chaves de API.'}), 400

        query = {
            'query': 'query { me { id name email subscription { documents credits } } }'
        }
        resp = requests.post(
            'https://api.autentique.com.br/v2/graphql',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json=query,
            timeout=35,
        )
        payload = resp.json()
        if resp.status_code >= 400 or payload.get('errors'):
            message = (payload.get('errors') or [{}])[0].get('message') or f'Erro HTTP {resp.status_code}'
            return jsonify({'error': message}), resp.status_code or 502

        me = ((payload.get('data') or {}).get('me') or {})
        subscription = me.get('subscription') or {}
        return jsonify({
            'ok': True,
            'usuario': {
                'id': me.get('id'),
                'name': me.get('name'),
                'email': me.get('email'),
            },
            'subscription': {
                'documents': subscription.get('documents'),
                'credits': subscription.get('credits'),
            },
        })
    except requests.RequestException as err:
        return jsonify({'error': f'Falha de conexão com a Autentique: {err}'}), 502
    except Exception as err:
        current_app.logger.error('GET /api/autentique/saldo: %s', err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/chaves', methods=['GET'])
def autentique_listar_chaves():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT valor FROM configuracoes WHERE chave=?",
            ('api_autentique_key',)
        ).fetchall()
        raw = rows[0]['valor'] if rows else ''
        keys = _parse_autentique_keys(raw)
        items = []
        for idx, key in enumerate(keys):
            masked = f'{key[:8]}...{key[-6:]}' if len(key) > 18 else key
            items.append({
                'id': idx + 1,
                'label': f'Chave {idx + 1}',
                'masked': masked,
                'value': key,
            })
        return jsonify(items)
    except Exception as err:
        current_app.logger.error('GET /api/autentique/chaves: %s', err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/enviar-whatsapp', methods=['POST'])
def autentique_enviar_whatsapp():
    data = request.get_json(silent=True) or {}
    doc_id = data.get('documento_id')
    signer_name = (data.get('signer_name') or '').strip()
    signer_phone_raw = (data.get('signer_phone') or '').strip()

    if not doc_id:
        return jsonify({'error': 'documento_id é obrigatório'}), 400
    if not signer_name:
        return jsonify({'error': 'Nome do signatário é obrigatório'}), 400
    if not signer_phone_raw:
        return jsonify({'error': 'Telefone/WhatsApp do signatário é obrigatório'}), 400

    signer_phone = _normalize_phone_br(signer_phone_raw)
    if len(signer_phone) < 12:
        return jsonify({'error': 'Telefone inválido. Informe DDD + número.'}), 400

    try:
        conn = get_db()
        api_key = _get_autentique_config(conn, api_key_override=(data.get('api_key') or '').strip())
        if not api_key:
            return jsonify({'error': 'Chave da Autentique não configurada. Acesse ADM -> Chaves de API.'}), 400

        row = conn.execute("SELECT * FROM documentos_centro WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Documento não encontrado'}), 404

        abs_path = os.path.join(DOCUMENTS_DIR, row['caminho_relativo'].replace('/', os.sep))
        if not os.path.exists(abs_path):
            return jsonify({'error': 'Arquivo físico não encontrado'}), 404

        mutation = """
mutation CreateDocument($document: DocumentInput!, $signers: [SignerInput!]!, $file: Upload!) {
  createDocument(document: $document, signers: $signers, file: $file) {
    id
    name
    signatures {
      public_id
      name
      email
      created_at
      action { name }
      link { short_link }
    }
  }
}
""".strip()

        operations = {
            'query': mutation,
            'variables': {
                'document': {
                    'name': row['nome_original'] or f'documento-{doc_id}.pdf',
                },
                'signers': [{
                    'name': signer_name,
                    'phone': signer_phone,
                    'delivery_method': 'DELIVERY_METHOD_WHATSAPP',
                    'action': 'SIGN',
                }],
                'file': None,
            }
        }
        file_map = {'0': ['variables.file']}

        mime, _ = mimetypes.guess_type(abs_path)
        with open(abs_path, 'rb') as fh:
            resp = requests.post(
                'https://api.autentique.com.br/v2/graphql',
                headers={
                    'Authorization': f'Bearer {api_key}',
                },
                data={
                    'operations': json.dumps(operations, ensure_ascii=False),
                    'map': json.dumps(file_map),
                },
                files={
                    '0': (row['nome_original'] or os.path.basename(abs_path), fh, mime or 'application/pdf'),
                },
                timeout=60,
            )

        payload = resp.json()
        if resp.status_code >= 400 or payload.get('errors'):
            message = (payload.get('errors') or [{}])[0].get('message') or f'Erro HTTP {resp.status_code}'
            return jsonify({
                'error': (
                    f'Falha ao criar documento na Autentique: {message}. '
                    'Observação: esta integração usa a mutation createDocument da API v2; '
                    'se sua conta tiver campos obrigatórios adicionais, podemos ajustar a payload.'
                )
            }), resp.status_code or 502

        document_data = ((payload.get('data') or {}).get('createDocument') or {})
        signatures = document_data.get('signatures') or []
        first_signature = signatures[0] if signatures else {}
        signature_link = ((first_signature.get('link') or {}).get('short_link') or '').strip()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO autentique_envios (
                documento_centro_id, autentique_document_id, autentique_signature_public_id,
                documento_nome, signatario_nome, signatario_phone, status, delivery_method,
                assinatura_link, criado_em, atualizado_em
            ) VALUES (?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
            """,
            (
                doc_id,
                document_data.get('id') or '',
                first_signature.get('public_id') or '',
                document_data.get('name') or row['nome_original'],
                signer_name,
                signer_phone,
                _autentique_guess_status(first_signature.get('status'), first_signature.get('created_at')),
                first_signature.get('delivery_method') or 'DELIVERY_METHOD_WHATSAPP',
                signature_link,
            )
        )
        envio_id = cur.lastrowid
        conn.commit()

        return jsonify({
            'ok': True,
            'envio_id': envio_id,
            'documento': {
                'id': document_data.get('id'),
                'name': document_data.get('name') or row['nome_original'],
            },
            'assinatura': {
                'public_id': first_signature.get('public_id'),
                'name': first_signature.get('name') or signer_name,
                'email': first_signature.get('email') or '',
                'phone': first_signature.get('phone') or signer_phone,
                'delivery_method': first_signature.get('delivery_method') or 'DELIVERY_METHOD_WHATSAPP',
                'link': signature_link,
            },
            'whatsapp_enviado': True,
            'phone_normalized': signer_phone,
        })
    except requests.RequestException as err:
        return jsonify({'error': f'Falha de conexão com a Autentique: {err}'}), 502
    except ValueError:
        return jsonify({'error': 'A resposta da Autentique não veio em JSON válido.'}), 502
    except Exception as err:
        current_app.logger.error('POST /api/autentique/enviar-whatsapp: %s', err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/envios', methods=['GET'])
def autentique_listar_envios():
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT
                e.*,
                d.nome_original AS documento_origem_nome,
                d.categoria AS documento_origem_categoria,
                s.nome_original AS documento_assinado_nome
            FROM autentique_envios e
            LEFT JOIN documentos_centro d ON d.id = e.documento_centro_id
            LEFT JOIN documentos_centro s ON s.id = e.assinado_doc_id
            ORDER BY e.id DESC
            LIMIT 200
        """).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as err:
        current_app.logger.error('GET /api/autentique/envios: %s', err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/envios/<int:envio_id>', methods=['DELETE'])
def autentique_excluir_envio(envio_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM autentique_envios WHERE id=?", (envio_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Envio não encontrado'}), 404
        conn.execute("DELETE FROM autentique_envios WHERE id=?", (envio_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as err:
        current_app.logger.error('DELETE /api/autentique/envios/%s: %s', envio_id, err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/contatos', methods=['GET'])
def autentique_listar_contatos():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM autentique_contatos ORDER BY nome COLLATE NOCASE ASC, id DESC"
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as err:
        current_app.logger.error('GET /api/autentique/contatos: %s', err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/contatos', methods=['POST'])
def autentique_salvar_contato():
    data = request.get_json(silent=True) or {}
    nome = (data.get('nome') or '').strip()
    phone_raw = (data.get('phone') or '').strip()

    if not nome:
        return jsonify({'error': 'Nome do contato é obrigatório'}), 400
    if not phone_raw:
        return jsonify({'error': 'WhatsApp do contato é obrigatório'}), 400

    phone = _normalize_phone_br(phone_raw)
    if len(re.sub(r'\D+', '', phone)) < 12:
        return jsonify({'error': 'WhatsApp inválido'}), 400

    try:
        conn = get_db()
        existing = conn.execute(
            "SELECT * FROM autentique_contatos WHERE phone=?",
            (phone,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE autentique_contatos SET nome=?, atualizado_em=datetime('now','localtime') WHERE id=?",
                (nome, existing['id'])
            )
            conn.commit()
            row = conn.execute("SELECT * FROM autentique_contatos WHERE id=?", (existing['id'],)).fetchone()
            return jsonify(row_to_dict(row))

        cur = conn.cursor()
        cur.execute(
            "INSERT INTO autentique_contatos (nome, phone, criado_em, atualizado_em) VALUES (?, ?, datetime('now','localtime'), datetime('now','localtime'))",
            (nome, phone)
        )
        new_id = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM autentique_contatos WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as err:
        current_app.logger.error('POST /api/autentique/contatos: %s', err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/contatos/<int:contato_id>', methods=['DELETE'])
def autentique_excluir_contato(contato_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM autentique_contatos WHERE id=?", (contato_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Contato não encontrado'}), 404
        conn.execute("DELETE FROM autentique_contatos WHERE id=?", (contato_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as err:
        current_app.logger.error('DELETE /api/autentique/contatos/%s: %s', contato_id, err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/envios/<int:envio_id>/download-assinado', methods=['GET'])
def autentique_download_assinado(envio_id):
    try:
        conn = get_db()
        row = conn.execute("""
            SELECT e.assinado_doc_id, d.nome_original, d.caminho_relativo
            FROM autentique_envios e
            LEFT JOIN documentos_centro d ON d.id = e.assinado_doc_id
            WHERE e.id=?
        """, (envio_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Envio não encontrado'}), 404
        if not row['assinado_doc_id'] or not row['caminho_relativo']:
            return jsonify({'error': 'Documento assinado ainda não está disponível'}), 404
        abs_path = os.path.join(DOCUMENTS_DIR, row['caminho_relativo'].replace('/', os.sep))
        if not os.path.exists(abs_path):
            return jsonify({'error': 'Arquivo assinado não encontrado no disco'}), 404
        mime, _ = mimetypes.guess_type(abs_path)
        return send_file(abs_path, mimetype=mime or 'application/pdf', as_attachment=True, download_name=row['nome_original'])
    except Exception as err:
        current_app.logger.error('GET /api/autentique/envios/%s/download-assinado: %s', envio_id, err)
        return jsonify({'error': str(err)}), 500


@bp.route('/autentique/webhook', methods=['POST'])
def autentique_webhook():
    payload = request.get_json(silent=True) or {}
    extracted = _autentique_extract_webhook(payload)
    if not extracted['document_id'] and not extracted['signature_public_id']:
        return jsonify({'error': 'Payload sem identificador de documento/assinatura'}), 400

    try:
        conn = get_db()
        params = []
        where = []
        if extracted['signature_public_id']:
            where.append("autentique_signature_public_id=?")
            params.append(extracted['signature_public_id'])
        if extracted['document_id']:
            where.append("autentique_document_id=?")
            params.append(extracted['document_id'])
        row = conn.execute(
            f"SELECT * FROM autentique_envios WHERE {' OR '.join(where)} ORDER BY id DESC LIMIT 1",
            tuple(params)
        ).fetchone()
        if not row:
            return jsonify({'ok': True, 'matched': False, 'message': 'Webhook recebido, mas nenhum envio local correspondeu.'})

        saved_doc = None
        signed_doc_id = row['assinado_doc_id']
        current_status = extracted['status'] if extracted['status'] != 'pendente' else (row['status'] or 'pendente')
        api_key = _get_autentique_config(conn)

        if current_status == 'assinado' and not signed_doc_id and extracted['download_url']:
            try:
                saved_doc = _autentique_save_signed_document(
                    extracted['download_url'],
                    row['documento_nome'] or 'documento',
                    api_key,
                )
                signed_doc_id = saved_doc['id']
            except Exception as download_err:
                current_app.logger.warning('Autentique webhook: falha ao baixar documento assinado: %s', download_err)

        conn.execute(
            """
            UPDATE autentique_envios
            SET status=?,
                delivery_method=?,
                assinatura_link=COALESCE(NULLIF(?, ''), assinatura_link),
                webhook_evento=?,
                webhook_payload=?,
                assinado_doc_id=?,
                assinado_em=CASE
                    WHEN ? <> '' THEN ?
                    WHEN ? = 'assinado' AND COALESCE(assinado_em,'') = '' THEN datetime('now','localtime')
                    ELSE assinado_em
                END,
                atualizado_em=datetime('now','localtime')
            WHERE id=?
            """,
            (
                current_status,
                extracted['delivery_method'] or row['delivery_method'] or 'DELIVERY_METHOD_WHATSAPP',
                extracted['signature_link'] or '',
                extracted['event_name'] or '',
                json.dumps(payload, ensure_ascii=False),
                signed_doc_id,
                extracted['signed_at'] or '',
                extracted['signed_at'] or '',
                current_status,
                row['id'],
            )
        )
        conn.commit()
        return jsonify({
            'ok': True,
            'matched': True,
            'envio_id': row['id'],
            'status': current_status,
            'assinado_doc_id': signed_doc_id,
            'download_salvo': bool(saved_doc),
        })
    except Exception as err:
        current_app.logger.error('POST /api/autentique/webhook: %s', err)
        return jsonify({'error': str(err)}), 500
