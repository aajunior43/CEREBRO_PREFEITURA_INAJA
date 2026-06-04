"""Blueprint: Despesas — CSV Import, IA, Empenhos CSV"""

import json
import io as _io
import datetime
from flask import Blueprint, request, jsonify
from routes._shared import get_db, row_to_dict, _get_openrouter_config, _build_ai_service, require_login

bp = Blueprint("despesas", __name__)


# ── DESPESAS (CSV Import) ─────────────────────────────────


@bp.route("/api/despesas/importacoes", methods=["GET"])
@require_login
def despesas_listar_importacoes():
    conn = get_db()
    tipo = (request.args.get("tipo") or "despesa").strip()
    if tipo not in ("despesa", "empenho"):
        return jsonify({"error": "tipo deve ser 'despesa' ou 'empenho'"}), 400
    table = "empenhos_importacoes" if tipo == "empenho" else "despesas_importacoes"
    try:
        rows = conn.execute(
            f"SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM {table} ORDER BY importado_em DESC"
        ).fetchall()
        result = [row_to_dict(r) for r in rows]
        for r in result:
            r["tipo"] = tipo
        return jsonify(result)
    except Exception:
        # Fallback to unified table
        rows = conn.execute(
            "SELECT id,tipo,periodo,descricao,arquivo,total_rows,importado_em FROM csv_importacoes WHERE tipo=? ORDER BY importado_em DESC",
            (tipo,),
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])


@bp.route("/api/despesas/importar", methods=["POST"])
@require_login
def despesas_importar():
    try:
        d = request.get_json(force=True)
        if not d:
            return jsonify({"error": "JSON inválido"}), 400
        periodo = (d.get("periodo") or "").strip()
        linhas = d.get("linhas", [])
        tipo = (d.get("tipo") or "despesa").strip()
        if tipo not in ("despesa", "empenho"):
            return jsonify({"error": "tipo deve ser 'despesa' ou 'empenho'"}), 400
        if not periodo:
            return jsonify({"error": "Período obrigatório"}), 400
        if not linhas:
            return jsonify({"error": "Nenhuma linha recebida"}), 400
        from datetime import datetime as _dt_now

        now = _dt_now.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cur = conn.cursor()
        
        # Use unified tables if available, fallback to old ones
        unified = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='csv_importacoes'").fetchone()
        if unified:
            cur.execute(
                "INSERT INTO csv_importacoes (tipo,periodo,descricao,arquivo,total_rows,colunas,importado_em) VALUES (?,?,?,?,?,?,?)",
                (
                    tipo, periodo,
                    (d.get("descricao") or "").strip(),
                    (d.get("arquivo") or "").strip(),
                    len(linhas),
                    json.dumps(d.get("colunas", []), ensure_ascii=False),
                    now,
                ),
            )
            imp_id = cur.lastrowid
            cur.executemany(
                "INSERT INTO csv_linhas (importacao_id,dados) VALUES (?,?)",
                [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas],
            )
            conn.commit()
            return jsonify(
                row_to_dict(
                    conn.execute(
                        "SELECT id,tipo,periodo,descricao,arquivo,total_rows,importado_em FROM csv_importacoes WHERE id=?",
                        (imp_id,),
                    ).fetchone()
                )
            ), 201
        else:
            old_table = "empenhos_importacoes" if tipo == "empenho" else "despesas_importacoes"
            old_lines = "empenhos_linhas" if tipo == "empenho" else "despesas_linhas"
            if tipo == "empenho":
                cur.execute(
                    f"INSERT INTO {old_table} (periodo,descricao,arquivo,total_rows,importado_em) VALUES (?,?,?,?,?)",
                    (
                        periodo,
                        (d.get("descricao") or "").strip(),
                        (d.get("arquivo") or "").strip(),
                        len(linhas),
                        now,
                    ),
                )
            else:
                cur.execute(
                    f"INSERT INTO {old_table} (periodo,descricao,arquivo,total_rows,colunas,importado_em) VALUES (?,?,?,?,?,?)",
                    (
                        periodo,
                        (d.get("descricao") or "").strip(),
                        (d.get("arquivo") or "").strip(),
                        len(linhas),
                        json.dumps(d.get("colunas", []), ensure_ascii=False),
                        now,
                    ),
                )
            imp_id = cur.lastrowid
            cur.executemany(
                f"INSERT INTO {old_lines} (importacao_id,dados) VALUES (?,?)",
                [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas],
            )
            conn.commit()
            return jsonify(
                row_to_dict(
                    conn.execute(
                        f"SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM {old_table} WHERE id=?",
                        (imp_id,),
                    ).fetchone()
                )
            ), 201
    except Exception as e:
        return jsonify({"error": "Erro ao salvar", "detail": str(e)}), 500


@bp.route("/api/despesas/importacoes/<int:imp_id>", methods=["GET"])
@require_login
def despesas_carregar(imp_id):
    conn = get_db()
    tipo = (request.args.get("tipo") or "despesa").strip()
    if tipo not in ("despesa", "empenho"):
        return jsonify({"error": "tipo deve ser 'despesa' ou 'empenho'"}), 400
    
    # Try unified first
    unified = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='csv_importacoes'").fetchone()
    if unified:
        imp = conn.execute(
            "SELECT id,tipo,periodo,descricao,arquivo,total_rows,colunas,importado_em FROM csv_importacoes WHERE id=? AND tipo=?",
            (imp_id, tipo),
        ).fetchone()
        if not imp:
            return jsonify({"error": "Importação não encontrada"}), 404
        linhas = [
            json.loads(r["dados"])
            for r in conn.execute(
                "SELECT dados FROM csv_linhas WHERE importacao_id=? ORDER BY id",
                (imp_id,),
            ).fetchall()
        ]
        imp_dict = row_to_dict(imp)
        imp_dict["colunas"] = json.loads(imp_dict.get("colunas") or "[]")
        return jsonify({"importacao": imp_dict, "linhas": linhas})
    
    table = "empenhos_importacoes" if tipo == "empenho" else "despesas_importacoes"
    lines_table = "empenhos_linhas" if tipo == "empenho" else "despesas_linhas"
    imp = conn.execute(
        f"SELECT * FROM {table} WHERE id=?",
        (imp_id,),
    ).fetchone()
    if not imp:
        return jsonify({"error": "Importação não encontrada"}), 404
    linhas = [
        json.loads(r["dados"])
        for r in conn.execute(
            f"SELECT dados FROM {lines_table} WHERE importacao_id=? ORDER BY id",
            (imp_id,),
        ).fetchall()
    ]
    imp_dict = row_to_dict(imp)
    if "colunas" in imp_dict:
        imp_dict["colunas"] = json.loads(imp_dict["colunas"] or "[]")
    return jsonify({"importacao": imp_dict, "linhas": linhas})


@bp.route("/api/despesas/importacoes/<int:imp_id>", methods=["DELETE"])
@require_login
def despesas_excluir(imp_id):
    conn = get_db()
    tipo = (request.args.get("tipo") or "despesa").strip()
    if tipo not in ("despesa", "empenho"):
        return jsonify({"error": "tipo deve ser 'despesa' ou 'empenho'"}), 400
    
    unified = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='csv_importacoes'").fetchone()
    if unified:
        conn.execute("DELETE FROM csv_linhas WHERE importacao_id=?", (imp_id,))
        conn.execute("DELETE FROM csv_importacoes WHERE id=?", (imp_id,))
        conn.commit()
        return jsonify({"ok": True})
    
    lines_table = "empenhos_linhas" if tipo == "empenho" else "despesas_linhas"
    table = "empenhos_importacoes" if tipo == "empenho" else "despesas_importacoes"
    conn.execute(f"DELETE FROM {lines_table} WHERE importacao_id=?", (imp_id,))
    conn.execute(f"DELETE FROM {table} WHERE id=?", (imp_id,))
    conn.commit()
    return jsonify({"ok": True})


@bp.route("/api/despesas/importacoes/<int:imp_id>/resumo", methods=["GET"])
@require_login
def despesas_resumo(imp_id):
    conn = get_db()
    unified = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='csv_importacoes'").fetchone()
    if unified:
        imp = conn.execute("SELECT * FROM csv_importacoes WHERE id=?", (imp_id,)).fetchone()
    else:
        imp = conn.execute("SELECT id,periodo,descricao,arquivo,total_rows,colunas,importado_em FROM despesas_importacoes WHERE id=?", (imp_id,)).fetchone()
    if not imp:
        return jsonify({"error": "Importação não encontrada"}), 404
    colunas = json.loads((imp["colunas"] if "colunas" in imp.keys() else imp.get("colunas")) or "[]")
    lines_table = "csv_linhas" if unified else "despesas_linhas"
    linhas = [
        json.loads(r["dados"])
        for r in conn.execute(
            f"SELECT dados FROM {lines_table} WHERE importacao_id=?", (imp_id,)
        ).fetchall()
    ]

    def parse_val(v):
        if not v:
            return 0.0
        try:
            return float(str(v).replace(".", "").replace(",", ".").strip())
        except Exception:
            return 0.0

    val_cols = [
        c
        for c in colunas
        if any(
            k in c.lower() for k in ["saldo", "valor", "empenhado", "liquidado", "pago"]
        )
    ]
    totais = {c: sum(parse_val(r.get(c, 0)) for r in linhas) for c in val_cols}

    def agrupar(col_key):
        grupos = {}
        for r in linhas:
            k = r.get(col_key) or "(Sem valor)"
            grupos[k] = grupos.get(k, 0) + 1
        return dict(sorted(grupos.items(), key=lambda x: -x[1])[:20])

    secretaria_col = next((c for c in colunas if "organograma" in c.lower()), None)
    funcao_col = next(
        (c for c in colunas if "função" in c.lower() or "funcao" in c.lower()), None
    )
    natureza_col = next(
        (
            c
            for c in colunas
            if "natureza" in c.lower()
            and "descrição" not in c.lower()
            and "descricao" not in c.lower()
        ),
        None,
    )
    recurso_col = next(
        (c for c in colunas if "recurso" in c.lower() and "descrição" not in c.lower()),
        None,
    )
    saldo_col = next((c for c in colunas if "saldo" in c.lower()), None)
    por_secretaria_valor = {}
    if secretaria_col and saldo_col:
        for r in linhas:
            k = r.get(secretaria_col) or "(Sem valor)"
            por_secretaria_valor[k] = por_secretaria_valor.get(k, 0) + parse_val(
                r.get(saldo_col, 0)
            )
        por_secretaria_valor = dict(
            sorted(por_secretaria_valor.items(), key=lambda x: -x[1])[:15]
        )
    return jsonify(
        {
            "importacao": {
                "id": imp["id"],
                "periodo": imp["periodo"],
                "descricao": imp["descricao"],
                "arquivo": imp["arquivo"],
                "total_rows": imp["total_rows"],
                "importado_em": imp["importado_em"],
            },
            "totais": totais,
            "por_secretaria_contagem": agrupar(secretaria_col)
            if secretaria_col
            else {},
            "por_secretaria_valor": por_secretaria_valor,
            "por_funcao": agrupar(funcao_col) if funcao_col else {},
            "por_natureza": agrupar(natureza_col) if natureza_col else {},
            "por_recurso": agrupar(recurso_col) if recurso_col else {},
            "saldo_col": saldo_col,
            "colunas": colunas,
        }
    )


# ── DESPESAS IA ──────────────────────────────────────────


@bp.route("/api/despesas/ia", methods=["POST"])
@require_login
def despesas_ia():
    from services.openrouter_service import AIServiceError

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()
    contexto = data.get("contexto") or {}
    pergunta = (data.get("pergunta") or "").strip()
    conn = get_db()
    api_key, model = _get_openrouter_config(conn)
    if not api_key:
        return jsonify({"error": "Chave do OpenRouter não configurada."}), 400
    today = datetime.date.today().strftime("%d/%m/%Y")

    def _fmt_brl(v):
        try:
            return (
                f"R$ {float(v):,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
        except Exception:
            return str(v)

    def _build_ctx_text(ctx):
        lines = [
            "=== DOTAÇÕES ORÇAMENTÁRIAS ===",
            f"Prefeitura de Inajá – PE",
            f"Período: {ctx.get('periodo', '?')} | Total: {ctx.get('total_rows', '?')}",
        ]
        totais = ctx.get("totais") or {}
        if totais:
            lines.append("\nTotais:")
            for k, v in totais.items():
                lines.append(f"  {k}: {_fmt_brl(v)}")
        sec = ctx.get("por_secretaria") or {}
        if sec:
            lines.append("\nSaldo por Secretaria (top 12):")
            for k, v in list(sec.items())[:12]:
                lines.append(f"  {k}: {_fmt_brl(v)}")
        nat = ctx.get("por_natureza") or {}
        if nat:
            lines.append("\nNatureza de Despesa (top 10):")
            for k, v in list(nat.items())[:10]:
                lines.append(f"  {k}: {v} dotações")
        return "\n".join(lines)

    system_prompts = {
        "analisar": f"Analista de orçamento público. Hoje é {today}. Faça análise completa com resumo, pontos de atenção, destaques e recomendações. Português do Brasil.",
        "chat": f"Assistente de orçamento público de Inajá/PE. Hoje é {today}. Responda perguntas sobre dotações. Português do Brasil.",
        "anomalias": f"Auditor de contas públicas. Hoje é {today}. Identifique anomalias e inconsistências. Português do Brasil.",
        "relatorio": f"Assessor técnico de finanças. Hoje é {today}. Gere relatório formal de execução orçamentária. Português do Brasil.",
        "remanejamento": f"Especialista em gestão orçamentária. Hoje é {today}. Sugira remanejamentos estratégicos. Português do Brasil.",
        "prioridades": f"Consultor de planejamento. Hoje é {today}. Identifique prioridades orçamentárias urgentes. Português do Brasil.",
        "cortes": f"Analista de eficiência. Hoje é {today}. Identifique contenção e contenção de gastos. Português do Brasil.",
    }
    if action not in system_prompts:
        return jsonify(
            {"error": f"Ação inválida. Use: {', '.join(system_prompts.keys())}"}
        ), 400
    messages = [
        {"role": "system", "content": system_prompts[action]},
        {
            "role": "user",
            "content": _build_ctx_text(contexto)
            + (f"\n\nPergunta: {pergunta}" if pergunta else ""),
        },
    ]
    try:
        response = _build_ai_service(api_key, model).chat_by_task(
            task_type="auditoria_documento",
            messages=messages,
            temperature=0.5,
            max_tokens=1800,
            use_cache=False,
            metadata={"feature": "despesas_ia", "action": action},
        )
        return jsonify(
            {
                "resultado": response.text,
                "action": action,
                "meta": {
                    "model": response.model,
                    "cached": response.cached,
                    "usage": response.usage,
                },
            }
        )
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as err:
        return jsonify({"error": str(err)}), 500


# ── EMPENHOS CSV (compat) ─────────────────────────────────


@bp.route("/api/empenhos-csv/importar", methods=["POST"])
@require_login
def empenhos_csv_importar():
    try:
        d = request.get_json(force=True) or {}
        periodo = (d.get("periodo") or "").strip()
        linhas = d.get("linhas", [])
        if not periodo or not linhas:
            return jsonify({"error": "Período e linhas obrigatórios"}), 400
        from datetime import datetime as _dt
        now = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cur = conn.cursor()
        unified = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='csv_importacoes'").fetchone()
        if unified:
            cur.execute(
                "INSERT INTO csv_importacoes (tipo,periodo,descricao,arquivo,total_rows,colunas,importado_em) VALUES (?,?,?,?,?,?,?)",
                ("empenho", periodo, (d.get("descricao") or "").strip(), (d.get("arquivo") or "").strip(), len(linhas), json.dumps(d.get("colunas", []), ensure_ascii=False), now),
            )
            imp_id = cur.lastrowid
            cur.executemany(
                "INSERT INTO csv_linhas (importacao_id,dados) VALUES (?,?)",
                [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas],
            )
            conn.commit()
            return jsonify(row_to_dict(conn.execute("SELECT * FROM csv_importacoes WHERE id=?", (imp_id,)).fetchone())), 201
        else:
            cur.execute(
                "INSERT INTO empenhos_importacoes (periodo,descricao,arquivo,total_rows,importado_em) VALUES (?,?,?,?,?)",
                (periodo, (d.get("descricao") or "").strip(), (d.get("arquivo") or "").strip(), len(linhas), now),
            )
            imp_id = cur.lastrowid
            cur.executemany(
                "INSERT INTO empenhos_linhas (importacao_id,dados) VALUES (?,?)",
                [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas],
            )
            conn.commit()
            return jsonify(row_to_dict(conn.execute("SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM empenhos_importacoes WHERE id=?", (imp_id,)).fetchone())), 201
    except Exception as e:
        return jsonify({"error": "Erro ao salvar", "detail": str(e)}), 500


@bp.route("/api/empenhos-csv/importacoes", methods=["GET"])
@require_login
def empenhos_csv_listar():
    conn = get_db()
    unified = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='csv_importacoes'").fetchone()
    if unified:
        rows = conn.execute(
            "SELECT id,tipo,periodo,descricao,arquivo,total_rows,importado_em FROM csv_importacoes WHERE tipo='empenho' ORDER BY importado_em DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM empenhos_importacoes ORDER BY importado_em DESC"
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@bp.route("/api/empenhos-csv/importacoes/<int:imp_id>", methods=["GET"])
@require_login
def empenhos_csv_carregar(imp_id):
    conn = get_db()
    unified = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='csv_importacoes'").fetchone()
    if unified:
        imp = conn.execute("SELECT * FROM csv_importacoes WHERE id=? AND tipo='empenho'", (imp_id,)).fetchone()
    else:
        imp = conn.execute("SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM empenhos_importacoes WHERE id=?", (imp_id,)).fetchone()
    if not imp:
        return jsonify({"error": "Importação não encontrada"}), 404
    lines_table = "csv_linhas" if unified else "empenhos_linhas"
    linhas = [json.loads(r["dados"]) for r in conn.execute(f"SELECT dados FROM {lines_table} WHERE importacao_id=? ORDER BY id", (imp_id,)).fetchall()]
    return jsonify({"importacao": row_to_dict(imp), "linhas": linhas})


@bp.route("/api/empenhos-csv/importacoes/<int:imp_id>", methods=["DELETE"])
@require_login
def empenhos_csv_excluir(imp_id):
    conn = get_db()
    unified = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='csv_importacoes'").fetchone()
    if unified:
        conn.execute("DELETE FROM csv_linhas WHERE importacao_id=?", (imp_id,))
        conn.execute("DELETE FROM csv_importacoes WHERE id=?", (imp_id,))
    else:
        conn.execute("DELETE FROM empenhos_linhas WHERE importacao_id=?", (imp_id,))
        conn.execute("DELETE FROM empenhos_importacoes WHERE id=?", (imp_id,))
    conn.commit()
    return jsonify({"ok": True})
