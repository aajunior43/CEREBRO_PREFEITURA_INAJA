"""Blueprint: Classificador de Despesa — IA"""

import json as _json
from flask import Blueprint, request, jsonify
from routes._shared import get_db, _get_openrouter_config, _build_ai_facade

bp = Blueprint("classificador", __name__)


@bp.route("/api/classificador-despesa", methods=["POST"])
def classificador_despesa():
    from services.openrouter_service import AIServiceError

    data = request.get_json(silent=True) or {}
    item = (data.get("item") or "").strip()
    if not item:
        return jsonify({"error": "Informe o item ou serviço."}), 400
    conn = get_db()
    api_key, model = _get_openrouter_config(conn)
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
                        f"{result.get('subelemento_codigo', '')} - {result.get('subelemento_nome', '')}".strip(
                            " -"
                        ),
                        result.get("justificativa", ""),
                        result.get("ponto_atencao", ""),
                        float(result.get("confianca", 0)),
                        _json.dumps(result, ensure_ascii=False),
                        used_model,
                        1 if used_cached else 0,
                    ),
                )
                conn.commit()
            except Exception:
                pass
            return jsonify(
                {
                    "resultado": result,
                    "meta": {
                        "model": used_model,
                        "cached": used_cached,
                        "tavily_search": tavily_used,
                    },
                }
            )
        return jsonify(
            {
                "resultado": {"item_analisado": item, "raw": result.content},
                "meta": {
                    "model": result.model,
                    "cached": result.cached,
                    "tavily_search": tavily_used,
                },
            }
        )
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp.route("/api/classificador-despesa/historico", methods=["GET"])
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
                resultado = _json.loads(row["resultado_json"] or "{}")
            except Exception:
                resultado = {}
            items.append(
                {
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
                }
            )
        return jsonify({"items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route(
    "/api/classificador-despesa/historico/<int:hid>", methods=["DELETE"]
)
def classificador_historico_delete(hid):
    try:
        conn = get_db()
        conn.execute("DELETE FROM classificador_despesa_historico WHERE id = ?", (hid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/classificador-despesa/historico", methods=["DELETE"])
def classificador_historico_limpar():
    try:
        conn = get_db()
        conn.execute("DELETE FROM classificador_despesa_historico")
        conn.commit()
        return jsonify({"ok": True, "cleared": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
