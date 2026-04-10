"""
Blueprint: Credores
CRUD, lixeira, restaurar, duplicar, envio Telegram
"""

import io as _io
import os
import subprocess
import tempfile
import time as _time

import requests
from flask import Blueprint, request, jsonify

from config import settings
from routes.helpers import (
    credor_payload,
    buscar_credor_duplicado,
    montar_filtros_credores,
    parse_bool,
)

bp = Blueprint("credores", __name__)


def get_db():
    from flask import g

    return g._get_db()


def row_to_dict(row):
    return dict(row)


def _should_include_summary(args) -> bool:
    raw = (args.get("include_summary") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@bp.route("/api/credores", methods=["GET"])
def get_credores():
    try:
        limit = max(1, min(request.args.get("limit", 50, type=int), 1000))
        offset = request.args.get("offset", 0, type=int)
        sort_col = (request.args.get("sort_col") or "departamento").strip().lower()
        sort_dir = (request.args.get("sort_dir") or "asc").strip().lower()
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "asc"
        sort_map = {
            "nome": "nome",
            "departamento": "departamento",
            "valor": "valor",
            "tipo": "tipo_valor",
            "tipo_valor": "tipo_valor",
            "validade": "validade",
        }
        order_by = sort_map.get(sort_col, "departamento")
        clauses, params = montar_filtros_credores(request.args)
        where_sql = " AND ".join(clauses)
        conn = get_db()
        total = conn.execute(
            f"SELECT COUNT(*) AS total FROM credores WHERE {where_sql}", params
        ).fetchone()["total"]
        rows = conn.execute(
            f"SELECT * FROM credores WHERE {where_sql} ORDER BY {order_by} {sort_dir}, nome ASC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        itens = [row_to_dict(r) for r in rows]
        resumo = None
        if _should_include_summary(request.args):
            resumo = conn.execute(
                """SELECT COUNT(*) AS total,
                    SUM(CASE WHEN COALESCE(tipo_valor,'FIXO') LIKE 'VAR%' THEN 1 ELSE 0 END) AS variaveis,
                    SUM(CASE WHEN COALESCE(tipo_valor,'FIXO') NOT LIKE 'VAR%' THEN 1 ELSE 0 END) AS fixos,
                    SUM(CASE WHEN COALESCE(cnpj,'')='' THEN 1 ELSE 0 END) AS sem_cnpj,
                    SUM(CASE WHEN COALESCE(email,'')='' THEN 1 ELSE 0 END) AS sem_email,
                    SUM(CASE WHEN COALESCE(validade,'')<>'' AND date(validade)<date('now','localtime') THEN 1 ELSE 0 END) AS vencidos,
                    SUM(CASE WHEN COALESCE(validade,'')<>'' AND date(validade)>=date('now','localtime') AND date(validade)<=date('now','localtime','+30 day') THEN 1 ELSE 0 END) AS vencendo_30
                FROM credores WHERE ativo=1"""
            ).fetchone()
        return jsonify(
            {
                "items": itens,
                "total": total,
                "limit": limit,
                "offset": offset,
                "summary": row_to_dict(resumo) if resumo else None,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores", methods=["POST"])
def add_credor():
    data = request.get_json(force=True) or {}
    payload, errors = credor_payload(data, partial=False)
    if errors:
        return jsonify({"error": errors[0], "errors": errors}), 400
    try:
        conn = get_db()
        duplicado, msg = buscar_credor_duplicado(conn, payload.get("cnpj", ""))
        if duplicado:
            return jsonify({"error": msg, "duplicado_id": duplicado["id"]}), 409
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO credores (nome,valor,descricao,cnpj,email,tipo_valor,solicitacao,pagamento,validade,departamento,obs) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                payload.get("nome", ""),
                payload.get("valor", 0),
                payload.get("descricao", ""),
                payload.get("cnpj", ""),
                payload.get("email", ""),
                payload.get("tipo_valor", "FIXO"),
                payload.get("solicitacao", ""),
                payload.get("pagamento", ""),
                payload.get("validade", ""),
                payload.get("departamento", ""),
                payload.get("obs", ""),
            ),
        )
        new_id = cur.lastrowid
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,detalhes) VALUES (?,?,?,?)",
            (
                "CRIAR",
                new_id,
                payload.get("nome", ""),
                payload.get("departamento", "") or "Cadastro de credor",
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>", methods=["PUT"])
def update_credor(cid):
    from routes.helpers import normalizar_cnpj

    data = request.get_json(force=True) or {}
    payload, errors = credor_payload(data, partial=False)
    if errors:
        return jsonify({"error": errors[0], "errors": errors}), 400
    try:
        conn = get_db()
        atual = conn.execute(
            "SELECT * FROM credores WHERE id=? AND ativo=1", (cid,)
        ).fetchone()
        if not atual:
            return jsonify({"error": "Credor não encontrado"}), 404
        cnpj_atual = normalizar_cnpj(atual["cnpj"] or "")
        cnpj_alterado = payload.get("cnpj", "") != cnpj_atual
        cnpj_verificar = payload.get("cnpj", "") if cnpj_alterado else ""
        duplicado, msg = buscar_credor_duplicado(conn, cnpj_verificar, ignore_id=cid)
        if duplicado:
            return jsonify({"error": msg, "duplicado_id": duplicado["id"]}), 409
        conn.execute(
            "UPDATE credores SET nome=?,valor=?,descricao=?,cnpj=?,email=?,tipo_valor=?,solicitacao=?,pagamento=?,validade=?,departamento=?,obs=? WHERE id=?",
            (
                payload.get("nome", ""),
                payload.get("valor", 0),
                payload.get("descricao", ""),
                payload.get("cnpj", ""),
                payload.get("email", ""),
                payload.get("tipo_valor", "FIXO"),
                payload.get("solicitacao", ""),
                payload.get("pagamento", ""),
                payload.get("validade", ""),
                payload.get("departamento", ""),
                payload.get("obs", ""),
                cid,
            ),
        )
        detalhes = []
        for key, label in (
            ("nome", "Nome"),
            ("departamento", "Departamento"),
            ("valor", "Valor"),
            ("tipo_valor", "Tipo"),
            ("validade", "Validade"),
            ("cnpj", "CNPJ"),
            ("email", "E-mail"),
        ):
            anterior = atual[key] if key in atual.keys() else ""
            novo = payload.get(key, "")
            if str(anterior or "") != str(novo or ""):
                detalhes.append(f"{label}: {anterior or '—'} → {novo or '—'}")
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,detalhes) VALUES (?,?,?,?)",
            (
                "EDITAR",
                cid,
                payload.get("nome", ""),
                " | ".join(detalhes) or "Cadastro atualizado",
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        return jsonify(row_to_dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>", methods=["DELETE"])
def delete_credor(cid):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM credores WHERE id=? AND ativo=1", (cid,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Credor não encontrado"}), 404
        conn.execute("UPDATE credores SET ativo=0 WHERE id=?", (cid,))
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,detalhes) VALUES (?,?,?,?)",
            ("EXCLUIR", cid, row["nome"], row["departamento"] or "Exclusão lógica"),
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/deletados", methods=["GET"])
def listar_deletados():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM credores WHERE ativo=0 ORDER BY atualizado_em DESC"
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>/restaurar", methods=["PUT"])
def restaurar_credor(cid):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM credores WHERE id=? AND ativo=0", (cid,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Credor não encontrado na lixeira"}), 404
        conflito = conn.execute(
            "SELECT id FROM credores WHERE ativo=1 AND UPPER(nome)=UPPER(?)",
            (row["nome"],),
        ).fetchone()
        if conflito:
            return jsonify(
                {"error": f'Já existe um credor ativo com o nome "{row["nome"]}"'}
            ), 409
        conn.execute(
            "UPDATE credores SET ativo=1, atualizado_em=datetime('now','localtime') WHERE id=?",
            (cid,),
        )
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,detalhes) VALUES (?,?,?,?)",
            (
                "RESTAURAR",
                cid,
                row["nome"],
                row["departamento"] or "Restaurado da lixeira",
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        return jsonify({"ok": True, "credor": row_to_dict(row)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>/duplicate", methods=["POST"])
def duplicate_credor(cid):
    try:
        conn = get_db()
        orig = conn.execute(
            "SELECT * FROM credores WHERE id=? AND ativo=1", (cid,)
        ).fetchone()
        if not orig:
            return jsonify({"error": "Credor original não encontrado"}), 404
        novo_nome_base = f"CÓPIA – {orig['nome']}"
        novo_nome = novo_nome_base
        sufixo = 2
        while conn.execute(
            "SELECT id FROM credores WHERE ativo=1 AND UPPER(nome)=?",
            (novo_nome.upper(),),
        ).fetchone():
            novo_nome = f"{novo_nome_base} ({sufixo})"
            sufixo += 1
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO credores (nome,valor,descricao,cnpj,email,tipo_valor,solicitacao,pagamento,validade,departamento,obs) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                novo_nome,
                orig["valor"],
                orig["descricao"] or "",
                "",
                orig["email"] or "",
                orig["tipo_valor"] or "FIXO",
                orig["solicitacao"] or "",
                orig["pagamento"] or "",
                orig["validade"] or "",
                orig["departamento"] or "",
                orig["obs"] or "",
            ),
        )
        new_id = cur.lastrowid
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,detalhes) VALUES (?,?,?,?)",
            (
                "CRIAR",
                new_id,
                novo_nome,
                f"Duplicado a partir do credor #{cid} ({orig['nome']})",
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>/enviar-telegram", methods=["POST"])
def enviar_telegram(cid):
    try:
        data = request.get_json(silent=True) or {}
        html = data.get("html", "")
        if not html:
            return jsonify({"error": "HTML não fornecido"}), 400

        env_file = os.path.join(settings.base_dir, ".env")
        telegram_token = ""
        chat_ids = []
        if os.path.exists(env_file):
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TELEGRAM_TOKEN="):
                        telegram_token = line.split("=", 1)[1].strip()
                    elif line.startswith("TELEGRAM_CHAT_ID="):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            chat_ids.append(val)

        targets_file = os.path.join(settings.base_dir, "telegram_chat_ids.txt")
        if os.path.exists(targets_file):
            raw = open(targets_file, encoding="utf-8").read().strip()
            for chunk in raw.replace("\n", ",").split(","):
                chunk = chunk.strip()
                if chunk and chunk not in chat_ids:
                    chat_ids.append(chunk)

        if not telegram_token:
            return jsonify({"error": "TELEGRAM_TOKEN não configurado no .env"}), 500
        if not chat_ids:
            return jsonify({"error": "Nenhum chat_id configurado"}), 500

        conn = get_db()
        credor = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        if not credor:
            return jsonify({"error": "Credor não encontrado"}), 404
        credor = dict(credor)

        fd_html, tmp_html = tempfile.mkstemp(suffix=".html")
        fd_pdf, tmp_pdf = tempfile.mkstemp(suffix=".pdf")
        os.close(fd_html)
        os.close(fd_pdf)
        try:
            with open(tmp_html, "w", encoding="utf-8") as f:
                f.write(html)
            edge_paths = [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]
            edge_exe = None
            for p in edge_paths:
                if os.path.exists(p):
                    edge_exe = p
                    break
            if not edge_exe:
                return jsonify({"error": "Microsoft Edge não encontrado"}), 500
            pdf_url = f"file:///{tmp_html.replace(os.sep, '/')}"
            subprocess.run(
                [
                    edge_exe,
                    "--headless",
                    "--disable-gpu",
                    "--no-margins",
                    f"--print-to-pdf={tmp_pdf}",
                    pdf_url,
                ],
                capture_output=True,
                timeout=30,
            )
            if not os.path.exists(tmp_pdf) or os.path.getsize(tmp_pdf) == 0:
                return jsonify({"error": "Falha ao gerar PDF"}), 500
            with open(tmp_pdf, "rb") as f:
                pdf_bytes = f.read()
        finally:
            for tmp in (tmp_html, tmp_pdf):
                try:
                    os.unlink(tmp)
                except Exception:
                    pass

        mes_nome = [
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]
        mes_label = mes_nome[int(_time.strftime("%m")) - 1]
        ano = _time.strftime("%Y")
        hoje = _time.strftime("%d/%m/%Y")
        filename = (
            f"solicitacao_{credor['nome'].replace(' ', '_')}_{mes_label}_{ano}.pdf"
        )

        sent = 0
        errors = []
        for chat_id in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{telegram_token}/sendDocument"
                resp = requests.post(
                    url,
                    data={
                        "chat_id": chat_id,
                        "caption": (
                            f"📋 *Solicitacao de Empenho*\n\n"
                            f"🏢 *Credor:* {credor['nome']}\n"
                            f"💰 *Valor:* R$ {float(credor.get('valor') or 0):,.2f}\n"
                            f"📂 *Departamento:* {credor.get('departamento') or '—'}\n"
                            f"📅 *Data:* {hoje}\n"
                            f"📆 *Referencia:* {mes_label}/{ano}\n\n"
                            f"_Enviado pelo Sistema de Empenhos — Prefeitura de Inajá_"
                        ),
                        "parse_mode": "Markdown",
                    },
                    files={
                        "document": (
                            filename,
                            _io.BytesIO(pdf_bytes),
                            "application/pdf",
                        )
                    },
                    timeout=30,
                )
                if resp.ok:
                    sent += 1
                else:
                    errors.append(f"Chat {chat_id}: {resp.text}")
            except Exception as e:
                errors.append(f"Chat {chat_id}: {str(e)}")

        if sent > 0:
            conn.execute(
                "INSERT INTO logs (acao,credor_id,credor_nome,detalhes) VALUES (?,?,?,?)",
                (
                    "TELEGRAM_ENVIO",
                    cid,
                    credor["nome"],
                    f"PDF enviado para {sent} chat(s) - {hoje}",
                ),
            )
            conn.commit()
            return jsonify({"ok": True, "sent": sent, "errors": errors})
        return jsonify({"error": "Falha ao enviar", "details": errors}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>/pdf-telegram", methods=["POST"])
def pdf_telegram(cid):
    """Gera PDF server-side e envia pelo Telegram. Usado pelo bot."""
    try:
        data = request.get_json(silent=True) or {}
        mes = data.get("mes")
        ano = data.get("ano")
        if not mes or not ano:
            hoje = _time.localtime()
            mes = hoje.tm_mon
            ano = hoje.tm_year
        mes = int(mes)
        ano = int(ano)

        conn = get_db()
        credor = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        if not credor:
            return jsonify({"error": "Credor não encontrado"}), 404
        credor = dict(credor)

        emp = conn.execute(
            "SELECT 1 FROM empenhos WHERE credor_id=? AND ano=? AND mes=? AND empenhado=1",
            (cid, ano, mes),
        ).fetchone()
        done = emp is not None

        is_var = (credor.get("tipo_valor") or "").upper().includes("VAR")
        if is_var and not credor.get("valor"):
            valor_str = "Valor variável"
        else:
            valor_str = f"R$ {float(credor.get('valor') or 0):,.2f}"

        mes_nomes = [
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]
        mes_nome = mes_nomes[mes - 1]

        campos = [
            ["Departamento Solicitante", credor.get("departamento")],
            ["Credor / Fornecedor", credor.get("nome")],
            ["CNPJ / CPF", credor.get("cnpj")],
            ["Descrição do Objeto / Serviço", credor.get("descricao")],
            ["Tipo de Valor", credor.get("tipo_valor")],
            ["Observações", credor.get("obs")],
        ]
        campos = [[l, v] for l, v in campos if v and str(v).strip()]
        table_rows = "".join(f"<tr><th>{l}</th><td>{v}</td></tr>" for l, v in campos)

        watermark = '<div class="watermark-done">EMPENHADO</div>' if done else ""

        brasao_path = os.path.join(settings.base_dir, "static", "img", "brasao.png")
        brasao_b64 = ""
        if os.path.exists(brasao_path):
            import base64

            with open(brasao_path, "rb") as f:
                brasao_b64 = (
                    "data:image/png;base64," + base64.b64encode(f.read()).decode()
                )
        if not brasao_b64:
            brasao_b64 = "/static/img/brasao.png"

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Solicitacao - {credor["nome"]}</title>
<style>
@page {{ margin: 12mm 15mm; size: A4 portrait; }}
* {{ margin:0; padding:0; box-sizing:border-box;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important; }}
body {{
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 11pt;
  color: #000;
  background: #fff;
}}
.doc-header {{
  display: flex;
  align-items: center;
  border: 2px solid #000;
  padding: 10px;
  margin-bottom: 20px;
  border-radius: 4px;
}}
.doc-header-brasao {{ width: 100px; height: auto; object-fit: contain; margin-right: 15px; }}
.doc-header-text {{ flex: 1; text-align: center; }}
.doc-header-text h1 {{ font-size: 14pt; font-weight: bold; text-transform: uppercase; margin-bottom: 2px; }}
.doc-header-text h2 {{ font-size: 11pt; font-weight: normal; margin-bottom: 4px; }}
.doc-header-text h3 {{ font-size: 12pt; font-weight: bold; text-transform: uppercase; border-top: 1px solid #000; margin-top: 4px; padding-top: 4px; }}
.doc-body {{ margin-bottom: 25px; position: relative; }}
.watermark-done {{
  position: absolute;
  top: 30%; left: 50%;
  transform: translate(-50%, -50%) rotate(-30deg);
  font-size: 80pt;
  font-weight: bold;
  color: rgba(58, 170, 110, 0.15);
  border: 8px solid rgba(58, 170, 110, 0.15);
  padding: 10px 40px;
  border-radius: 20px;
  user-select: none;
  pointer-events: none;
  z-index: 0;
}}
table.doc-table {{
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 15px;
  position: relative;
  z-index: 1;
}}
table.doc-table th, table.doc-table td {{
  border: 1px solid #000;
  padding: 8px;
  vertical-align: middle;
}}
table.doc-table th {{
  background: #f0f0f0;
  text-transform: uppercase;
  font-size: 9pt;
  width: 30%;
  text-align: left;
}}
table.doc-table td {{ font-size: 10pt; font-weight: 500; }}
.valor-box {{
  border: 2px solid #000;
  background: #fdfdfd;
  padding: 12px;
  text-align: center;
  margin-bottom: 30px;
  border-radius: 4px;
}}
.vb-label {{ font-size: 11pt; font-weight: bold; text-transform: uppercase; margin-bottom: 5px; }}
.vb-value {{ font-size: 18pt; font-weight: bold; }}
.sign-date {{
  text-align: right; margin-bottom: 40px; font-size: 11pt;
}}
.sign-section {{
  display: flex;
  justify-content: space-around;
  margin-top: 50px;
}}
.sign-block {{ text-align: center; width: 40%; }}
.sign-line-top {{
  border-bottom: 1px solid #000;
  margin-bottom: 8px;
  height: 40px;
}}
.sign-label {{ font-size: 10pt; font-weight: bold; text-transform: uppercase; }}
.sign-sub {{ font-size: 9pt; margin-top: 2px; }}
</style>
</head>
<body>
<div style="position: relative;">
  <div class="doc-header">
    <img class="doc-header-brasao" src="{brasao_b64}" alt="Brasão" />
    <div class="doc-header-text">
      <h2>Prefeitura Municipal de Inajá</h2>
      <h3>Solicitação de Empenho</h3>
    </div>
  </div>
  <div class="doc-body">
    {watermark}
    <table class="doc-table">{table_rows}</table>
    <div class="valor-box">
      <div class="vb-label">Valor do Empenho</div>
      <div class="vb-value">{valor_str}</div>
    </div>
    <div class="sign-date">
      Inajá / PR, _____ de ___________________ de {ano}.
    </div>
    <div class="sign-section">
      <div class="sign-block" style="width: 50%;">
         <div class="sign-line-top"></div>
         <div class="sign-label">Ordenador de Despesa</div>
         <div class="sign-sub">Prefeitura Municipal de Inajá</div>
      </div>
    </div>
  </div>
</div>
</body></html>"""

        fd_html, tmp_html = tempfile.mkstemp(suffix=".html")
        fd_pdf, tmp_pdf = tempfile.mkstemp(suffix=".pdf")
        os.close(fd_html)
        os.close(fd_pdf)
        try:
            with open(tmp_html, "w", encoding="utf-8") as f:
                f.write(html)
            edge_paths = [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]
            edge_exe = None
            for p in edge_paths:
                if os.path.exists(p):
                    edge_exe = p
                    break
            if not edge_exe:
                return jsonify({"error": "Microsoft Edge não encontrado"}), 500
            pdf_url = f"file:///{tmp_html.replace(os.sep, '/')}"
            subprocess.run(
                [
                    edge_exe,
                    "--headless",
                    "--disable-gpu",
                    "--no-margins",
                    f"--print-to-pdf={tmp_pdf}",
                    pdf_url,
                ],
                capture_output=True,
                timeout=30,
            )
            if not os.path.exists(tmp_pdf) or os.path.getsize(tmp_pdf) == 0:
                return jsonify({"error": "Falha ao gerar PDF"}), 500
            with open(tmp_pdf, "rb") as f:
                pdf_bytes = f.read()
        finally:
            for tmp in (tmp_html, tmp_pdf):
                try:
                    os.unlink(tmp)
                except Exception:
                    pass

        hoje_str = _time.strftime("%d/%m/%Y")
        filename = (
            f"solicitacao_{credor['nome'].replace(' ', '_')}_{mes_nome}_{ano}.pdf"
        )

        env_file = os.path.join(settings.base_dir, ".env")
        telegram_token = ""
        chat_ids = []
        if os.path.exists(env_file):
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TELEGRAM_TOKEN="):
                        telegram_token = line.split("=", 1)[1].strip()
                    elif line.startswith("TELEGRAM_CHAT_ID="):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            chat_ids.append(val)

        targets_file = os.path.join(settings.base_dir, "telegram_chat_ids.txt")
        if os.path.exists(targets_file):
            raw = open(targets_file, encoding="utf-8").read().strip()
            for chunk in raw.replace("\n", ",").split(","):
                chunk = chunk.strip()
                if chunk and chunk not in chat_ids:
                    chat_ids.append(chunk)

        if not telegram_token:
            return jsonify({"error": "TELEGRAM_TOKEN não configurado"}), 500
        if not chat_ids:
            return jsonify({"error": "Nenhum chat_id configurado"}), 500

        sent = 0
        errors = []
        for chat_id in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{telegram_token}/sendDocument"
                resp = requests.post(
                    url,
                    data={
                        "chat_id": chat_id,
                        "caption": (
                            f"📋 *Solicitacao de Empenho*\n\n"
                            f"🏢 *Credor:* {credor['nome']}\n"
                            f"💰 *Valor:* R$ {float(credor.get('valor') or 0):,.2f}\n"
                            f"📂 *Departamento:* {credor.get('departamento') or '—'}\n"
                            f"📅 *Data:* {hoje_str}\n"
                            f"📆 *Referencia:* {mes_nome}/{ano}\n\n"
                            f"_Enviado pelo Sistema de Empenhos — Prefeitura de Inajá_"
                        ),
                        "parse_mode": "Markdown",
                    },
                    files={
                        "document": (
                            filename,
                            _io.BytesIO(pdf_bytes),
                            "application/pdf",
                        )
                    },
                    timeout=30,
                )
                if resp.ok:
                    sent += 1
                else:
                    errors.append(f"Chat {chat_id}: {resp.text}")
            except Exception as e:
                errors.append(f"Chat {chat_id}: {str(e)}")

        if sent > 0:
            conn.execute(
                "INSERT INTO logs (acao,credor_id,credor_nome,detalhes) VALUES (?,?,?,?)",
                (
                    "TELEGRAM_ENVIO",
                    cid,
                    credor["nome"],
                    f"PDF enviado para {sent} chat(s) - {hoje_str}",
                ),
            )
            conn.commit()
            return jsonify({"ok": True, "sent": sent, "errors": errors})
        return jsonify({"error": "Falha ao enviar", "details": errors}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
