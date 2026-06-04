"""Blueprint: Prazos"""

import time as _time
from flask import Blueprint, request, jsonify
from routes._shared import require_login

bp = Blueprint("prazos", __name__)


def get_db():
    from flask import g
    return g._get_db()


@bp.route("/api/prazos", methods=["GET"])
@require_login
def prazos_listar():
    try:
        limit = max(1, min(request.args.get("limit", 100, type=int), 1000))
        offset = max(0, request.args.get("offset", 0, type=int))
        conn = get_db()
        status_f = request.args.get("status", "ativos")
        categoria = request.args.get("categoria", "")
        clauses, params = [], []
        if status_f == "ativos":
            clauses.append("resolvido=0")
        elif status_f == "resolvidos":
            clauses.append("resolvido=1")
        if categoria:
            clauses.append("categoria=?")
            params.append(categoria)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        total = conn.execute(
            f"SELECT COUNT(*) FROM prazos {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM prazos {where} ORDER BY data_limite ASC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return jsonify({"items": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/prazos/resumo", methods=["GET"])
@require_login
def prazos_resumo():
    try:
        conn = get_db()
        hoje = _time.strftime("%Y-%m-%d")
        em7 = _time.strftime("%Y-%m-%d", _time.localtime(_time.time() + 7 * 86400))
        em30 = _time.strftime("%Y-%m-%d", _time.localtime(_time.time() + 30 * 86400))
        return jsonify(
            {
                "vencidos": conn.execute(
                    "SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite<?",
                    (hoje,),
                ).fetchone()[0],
                "urgentes": conn.execute(
                    "SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite>=? AND data_limite<=?",
                    (hoje, em7),
                ).fetchone()[0],
                "atencao": conn.execute(
                    "SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite>? AND data_limite<=?",
                    (em7, em30),
                ).fetchone()[0],
                "ok": conn.execute(
                    "SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite>?",
                    (em30,),
                ).fetchone()[0],
                "total": conn.execute(
                    "SELECT COUNT(*) FROM prazos WHERE resolvido=0"
                ).fetchone()[0],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/prazos", methods=["POST"])
@require_login
def prazos_criar():
    try:
        data = request.get_json(force=True) or {}
        titulo = (data.get("titulo") or "").strip()
        data_limite = (data.get("data_limite") or "").strip()
        if not titulo or not data_limite:
            return jsonify({"error": "titulo e data_limite são obrigatórios"}), 400
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO prazos (titulo,descricao,data_limite,categoria) VALUES (?,?,?,?)",
            (
                titulo,
                (data.get("descricao") or "").strip(),
                data_limite,
                (data.get("categoria") or "geral").strip(),
            ),
        )
        conn.commit()
        return jsonify(
            dict(
                conn.execute(
                    "SELECT * FROM prazos WHERE id=?", (cur.lastrowid,)
                ).fetchone()
            )
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/prazos/<int:prazo_id>", methods=["PUT"])
@require_login
def prazos_atualizar(prazo_id):
    try:
        data = request.get_json(force=True) or {}
        conn = get_db()
        if not conn.execute("SELECT * FROM prazos WHERE id=?", (prazo_id,)).fetchone():
            return jsonify({"error": "Prazo não encontrado"}), 404
        fields = {}
        for k in ("titulo", "descricao", "data_limite", "categoria"):
            if k in data:
                fields[k] = (data[k] or "").strip()
        if "resolvido" in data:
            fields["resolvido"] = 1 if data["resolvido"] else 0
        if not fields:
            return jsonify(
                dict(
                    conn.execute(
                        "SELECT * FROM prazos WHERE id=?", (prazo_id,)
                    ).fetchone()
                )
            )
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(
            f"UPDATE prazos SET {set_clause} WHERE id=?",
            list(fields.values()) + [prazo_id],
        )
        conn.commit()
        return jsonify(
            dict(
                conn.execute("SELECT * FROM prazos WHERE id=?", (prazo_id,)).fetchone()
            )
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/prazos/<int:prazo_id>", methods=["DELETE"])
@require_login
def prazos_excluir(prazo_id):
    try:
        conn = get_db()
        if not conn.execute("SELECT id FROM prazos WHERE id=?", (prazo_id,)).fetchone():
            return jsonify({"error": "Prazo não encontrado"}), 404
        conn.execute("DELETE FROM prazos WHERE id=?", (prazo_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/prazos/ai/extrair", methods=["POST"])
@require_login
def prazos_ai_extrair():
    from services.openrouter_service import AIServiceError
    import os
    
    try:
        conn = get_db()
        texto_conteudo = ""
        
        # 1. Verifica se foi enviado arquivo ou texto
        if "arquivo" in request.files:
            file = request.files["arquivo"]
            if file and file.filename:
                # Salva o arquivo temporariamente no diretório tmp
                from config import settings
                temp_dir = os.path.join(settings.base_dir, "tmp")
                os.makedirs(temp_dir, exist_ok=True)
                import uuid
                temp_path = os.path.join(temp_dir, f"temp_upload_{uuid.uuid4().hex}_{file.filename}")
                file.save(temp_path)
                
                try:
                    from renomer.file_processor import extrair_texto
                    from pathlib import Path
                    texto_conteudo = extrair_texto(Path(temp_path)) or ""
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
        else:
            # Tenta pegar do corpo JSON
            data = request.get_json(silent=True) or {}
            texto_conteudo = (data.get("texto") or "").strip()
            
        if not texto_conteudo:
            return jsonify({"error": "Nenhum texto ou arquivo válido foi fornecido."}), 400
            
        # 2. Configura chaves do OpenRouter
        from routes._shared import _get_openrouter_config, _build_ai_service
        api_key, model = _get_openrouter_config(conn)
        if not api_key:
            return jsonify({"error": "Chave API OpenRouter não configurada."}), 400
            
        # 3. Executa a IA
        prompt = f"""Você é o Cérebro Municipal, assistente de IA da Prefeitura de Inajá/PE.
Analise o texto a seguir (um edital, contrato, diário oficial, convite, ou ofício) e identifique todas as datas limite e prazos nele contidos.
Para cada prazo identificado, retorne um objeto com:
- "titulo": Nome do prazo ou obrigação de forma clara, resumida e direta.
- "data_limite": A data no formato AAAA-MM-DD. Se a data estiver implícita (ex: "15 dias a contar de hoje"), estime a data a partir de hoje ({_time.strftime("%d/%m/%Y")}).
- "categoria": Classifique em uma das seguintes categorias: "contrato", "licitacao", "processo", "oficio", "financeiro", "outro".
- "descricao": Breve descrição do contexto do prazo.

Responda APENAS com JSON no formato exato:
{{"prazos": [{{"titulo": "...", "data_limite": "AAAA-MM-DD", "categoria": "contrato|licitacao|...", "descricao": "..."}}]}}

TEXTO PARA ANÁLISE:
{texto_conteudo[:8000]}
"""

        response = _build_ai_service(api_key, model).chat_by_task(
            task_type="chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500,
            use_cache=True,
            metadata={"feature": "extrair_prazos_ia"},
        )
        
        from services.openrouter_service import extract_json_block
        parsed = extract_json_block(response.text)
        
        if not parsed or not isinstance(parsed, dict) or "prazos" not in parsed:
            return jsonify({"error": "Não foi possível extrair prazos estruturados do texto."}), 502
            
        return jsonify({
            "prazos": parsed["prazos"],
            "model": response.model,
            "usage": response.usage
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
