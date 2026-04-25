"""
app/routes/classificador.py — AI expense classifier (migrated from routes/all_routes.py)
"""
import json
import os
import sqlite3
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict
from app.utils.ai_service_factory import get_openrouter_config, build_ai_facade
from config import settings

bp = Blueprint("classificador", __name__)


def _build_ai_service(api_key, model):
    """Wrapper para manter compatibilidade com código existente"""
    facade, _ = build_ai_facade(api_key=api_key, default_model=model)
    return facade


def _build_ai_facade(api_key, model):
    """Deprecated: usar ai_service_factory diretamente"""
    from services.ai_tasks import AITaskFacade
    return AITaskFacade(_build_ai_service(api_key, model))


@bp.route("/classificador-despesa", methods=["POST"])
def classificador_despesa():
    from services.openrouter_service import AIServiceError

    data = request.get_json(silent=True) or {}
    item = (data.get("item") or "").strip()
    if not item:
        return jsonify({"error": "Informe o item ou serviço."}), 400
    conn = get_db()
    api_key, model = get_openrouter_config(conn)
    if not api_key:
        return jsonify({"error": "Chave do OpenRouter não configurada."}), 400
    web_context = ""
    tavily_key = (data.get("tavily_key") or "").strip()
    if not tavily_key:
        rows = conn.execute(
            "SELECT valor FROM configuracoes WHERE chave=?", ("api_tavily_key",)
        ).fetchall()
        tavily_key = rows[0]["valor"] if rows else ""
    tavily_used = False
    if tavily_key:
        try:
            from services.tavily_service import build_tavily_service
            tavily = build_tavily_service(api_key=tavily_key, logger=None)
            web_context = tavily.search_as_context(
                f"classificação contábil despesa pública {item} TCE MCASP elemento despesa",
                max_results=3,
            )
            tavily_used = bool(web_context)
        except Exception:
            pass
    try:
        facade = _build_ai_facade(api_key, model)
        result = facade.classificar_despesa(item, web_context=web_context)
        used_model, used_cached = model, False
        if isinstance(result, dict):
            used_model = result.pop("_model", model)
            used_cached = result.pop("_cached", False)
            try:
                conn.execute(
                    "INSERT INTO classificador_despesa_historico (item,codigo_completo,grupo,modalidade,elemento,subelemento,justificativa,ponto_atencao,confianca,resultado_json,model,cached) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        item,
                        result.get("codigo_completo", ""),
                        result.get("grupo", ""),
                        result.get("modalidade", ""),
                        result.get("elemento", ""),
                        f"{result.get('subelemento_codigo', '')} - {result.get('subelemento_nome', '')}".strip(" -"),
                        result.get("justificativa", ""),
                        result.get("ponto_atencao", ""),
                        float(result.get("confianca", 0)),
                        json.dumps(result, ensure_ascii=False),
                        used_model,
                        1 if used_cached else 0,
                    ),
                )
                conn.commit()
            except Exception:
                pass
            return jsonify({
                "resultado": result,
                "meta": {
                    "model": used_model,
                    "cached": used_cached,
                    "tavily_search": tavily_used,
                },
            })
        return jsonify({
            "resultado": {"item_analisado": item, "raw": result.content},
            "meta": {
                "model": result.model,
                "cached": result.cached,
                "tavily_search": tavily_used,
            },
        })
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp.route("/classificador-despesa/historico", methods=["GET"])
def classificador_historico():
    try:
        conn = get_db()
        try:
            limit = min(max(int(request.args.get("limit", 30) or 30), 1), 100)
        except (TypeError, ValueError):
            limit = 30
        rows = conn.execute(
            "SELECT id,item,codigo_completo,grupo,modalidade,elemento,subelemento,justificativa,ponto_atencao,confianca,resultado_json,model,cached,criado_em FROM classificador_despesa_historico ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        items = []
        for row in rows:
            try:
                resultado = json.loads(row["resultado_json"] or "{}")
            except Exception:
                resultado = {}
            items.append({
                "id": row["id"],
                "item": row["item"],
                "codigo_completo": row["codigo_completo"],
                "grupo": row["grupo"],
                "modalidade": row["modalidade"],
                "elemento": row["elemento"],
                "subelemento": row["subelemento"],
                "justificativa": row["justificativa"],
                "ponto_atencao": row["ponto_atencao"],
                "confianca": row["confianca"],
                "resultado": resultado,
                "model": row["model"],
                "cached": bool(row["cached"]),
                "criado_em": row["criado_em"],
            })
        return jsonify({"items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/classificador-despesa/historico/<int:hid>", methods=["DELETE"])
def classificador_historico_delete(hid):
    try:
        conn = get_db()
        conn.execute("DELETE FROM classificador_despesa_historico WHERE id = ?", (hid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/classificador-despesa/historico", methods=["DELETE"])
def classificador_historico_limpar():
    try:
        conn = get_db()
        conn.execute("DELETE FROM classificador_despesa_historico")
        conn.commit()
        return jsonify({"ok": True, "cleared": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/classificador-despesa/elementos", methods=["GET"])
def obter_elementos():
    """Obter todos os elementos de despesa para autocomplete"""
    elementos = [
        {"codigo": "04", "nome": "Locação de Imóveis"},
        {"codigo": "08", "nome": "Outros Benefícios Assistenciais"},
        {"codigo": "11", "nome": "Vencimentos e Vantagens Fixas"},
        {"codigo": "13", "nome": "Obrigações Patronais"},
        {"codigo": "14", "nome": "Diárias"},
        {"codigo": "30", "nome": "Material de Consumo"},
        {"codigo": "31", "nome": "Premiações Culturais, Esportivas"},
        {"codigo": "32", "nome": "Material para Distribuição Gratuita"},
        {"codigo": "33", "nome": "Passagens e Deslocamentos"},
        {"codigo": "34", "nome": "Equipamentos para Empresas Públicas"},
        {"codigo": "35", "nome": "Serviços de Transporte"},
        {"codigo": "36", "nome": "Serviços - Pessoa Física"},
        {"codigo": "39", "nome": "Serviços - Pessoa Jurídica"},
        {"codigo": "47", "nome": "Obrigações Tributárias"},
        {"codigo": "48", "nome": "Auxílio Financeiro a Entidades"},
        {"codigo": "51", "nome": "Obras e Instalações"},
        {"codigo": "52", "nome": "Equipamentos e Material Permanente"},
        {"codigo": "61", "nome": "Aquisição de Imóveis"},
        {"codigo": "63", "nome": "Aquisição de Títulos"},
        {"codigo": "64", "nome": "Concessão de Subvenções"},
        {"codigo": "71", "nome": "Concessão de Empréstimos"},
        {"codigo": "92", "nome": "Despesas de Exercícios Anteriores"},
        {"codigo": "93", "nome": "Indenizações"}
    ]
    return jsonify(elementos)


@bp.route("/classificador-despesa/validadas", methods=["GET"])
def classificacoes_validadas():
    """Obter classificações validadas (aprendizado contínuo)"""
    import json
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'empenhos.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Criar tabela se não existir
    conn.execute("""CREATE TABLE IF NOT EXISTS classificacoes_validadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item TEXT NOT NULL,
        elemento TEXT NOT NULL,
        codigo_completo TEXT NOT NULL,
        justificativa TEXT,
        validado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        vezes_usado INTEGER DEFAULT 1
    )""")
    conn.commit()
    
    limit = request.args.get('limit', 50)
    search = request.args.get('search', '')
    
    if search:
        rows = conn.execute(
            "SELECT * FROM classificacoes_validadas WHERE item LIKE ? ORDER BY vezes_usado DESC, validado_em DESC LIMIT ?",
            (f"%{search}%", limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM classificacoes_validadas ORDER BY vezes_usado DESC, validado_em DESC LIMIT ?",
            (limit,)
        ).fetchall()
    
    conn.close()
    return jsonify([dict(row) for row in rows])


@bp.route("/classificador-despesa/validar", methods=["POST"])
def validar_classificacao():
    """Validar classificação para aprendizado contínuo"""
    data = request.get_json()
    
    item = data.get('item', '').strip()
    elemento = data.get('elemento', '').strip()
    codigo_completo = data.get('codigo_completo', '').strip()
    justificativa = data.get('justificativa', '').strip()
    
    if not item or not elemento:
        return jsonify({"error": "Item e elemento são obrigatórios"}), 400
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'empenhos.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Criar tabela se não existir
    conn.execute("""CREATE TABLE IF NOT EXISTS classificacoes_validadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item TEXT NOT NULL,
        elemento TEXT NOT NULL,
        codigo_completo TEXT NOT NULL,
        justificativa TEXT,
        validado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        vezes_usado INTEGER DEFAULT 1
    )""")
    
    # Verificar se já existe
    existing = conn.execute(
        "SELECT id, vezes_usado FROM classificacoes_validadas WHERE item = ? AND elemento = ?",
        (item, elemento)
    ).fetchone()
    
    if existing:
        conn.execute(
            "UPDATE classificacoes_validadas SET vezes_usado = vezes_usado + 1, validado_em = CURRENT_TIMESTAMP WHERE id = ?",
            (existing['id'],)
        )
    else:
        conn.execute(
            "INSERT INTO classificacoes_validadas (item, elemento, codigo_completo, justificativa) VALUES (?, ?, ?, ?)",
            (item, elemento, codigo_completo, justificativa)
        )
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Classificação validada!"})


@bp.route("/classificador-despesa/sugestoes", methods=["GET"])
def sugestoes_classificacao():
    """Obter sugestões de classificação baseadas em histórico"""
    search = request.args.get('q', '').strip()
    
    if not search or len(search) < 3:
        return jsonify([])
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'empenhos.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Buscar no histórico de classificações
    rows = conn.execute(
        """SELECT item, codigo_completo, elemento, grupo, modalidade, 
                  COUNT(*) as vezes, 
                  MAX(classificado_em) as ultima_vez
           FROM classificador_despesa_historico 
           WHERE item LIKE ? 
           GROUP BY item, codigo_completo 
           ORDER BY vezes DESC, ultima_vez DESC 
           LIMIT 10""",
        (f"%{search}%",)
    ).fetchall()
    
    conn.close()
    
    sugestoes = []
    for row in rows:
        sugestoes.append({
            "item": row["item"],
            "codigo_completo": row["codigo_completo"],
            "elemento": row["elemento"],
            "grupo": row["grupo"],
            "vezes_usado": row["vezes"]
        })
    
    return jsonify(sugestoes)
