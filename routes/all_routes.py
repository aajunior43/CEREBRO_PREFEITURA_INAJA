"""Blueprints: Prazos, Protocolos, RPAs, Fornecimento, PDF, Despesas, CNPJ, IA, Config, Logs, Auth, Extratos, Empenho Assistente, Classificador"""

import json
import os
import re
import time as _time
from io import BytesIO as _io
from flask import Blueprint, request, jsonify, send_file

from config import settings

bp_prazos = Blueprint("prazos", __name__)
bp_protocolos = Blueprint("protocolos", __name__)
bp_rpas = Blueprint("rpas", __name__)
bp_fornecimento = Blueprint("fornecimento", __name__)
bp_pdf = Blueprint("pdf", __name__)
bp_despesas = Blueprint("despesas", __name__)
bp_cnpj = Blueprint("cnpj", __name__)
bp_ia = Blueprint("ia", __name__)
bp_config = Blueprint("config", __name__)
bp_logs = Blueprint("logs", __name__)
bp_auth = Blueprint("auth", __name__)
bp_extratos = Blueprint("extratos", __name__)
bp_empenho_assistente = Blueprint("empenho_assistente", __name__)
bp_classificador = Blueprint("classificador", __name__)


def get_db():
    from flask import g

    return g._get_db()


def row_to_dict(row):
    return dict(row)


def _get_openrouter_config(conn, api_key_override: str = "", model_override: str = ""):
    rows = conn.execute(
        "SELECT chave,valor FROM configuracoes WHERE chave IN (?,?)",
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


def _build_ai_service(api_key: str, model: str):
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


def _build_ai_facade(api_key: str, model: str):
    from services.ai_tasks import AITaskFacade

    return AITaskFacade(_build_ai_service(api_key, model))


def _extract_json_block(text: str):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return json.loads(match.group(1))
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s : e + 1])
        except Exception:
            pass
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e != -1 and e > s:
        return json.loads(text[s : e + 1])
    raise ValueError("Formato inválido")


# ── PRAZOS ───────────────────────────────────────────────────
@bp_prazos.route("/api/prazos", methods=["GET"])
def prazos_listar():
    try:
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
        rows = conn.execute(
            f"SELECT * FROM prazos {where} ORDER BY data_limite ASC", params
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_prazos.route("/api/prazos/resumo", methods=["GET"])
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


@bp_prazos.route("/api/prazos", methods=["POST"])
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


@bp_prazos.route("/api/prazos/<int:prazo_id>", methods=["PUT"])
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


@bp_prazos.route("/api/prazos/<int:prazo_id>", methods=["DELETE"])
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


# ── PROTOCOLOS ───────────────────────────────────────────────
def _proximo_numero_protocolo(conn):
    ano = _time.strftime("%Y")
    ultimo = conn.execute(
        "SELECT numero FROM protocolos WHERE numero LIKE ? ORDER BY id DESC LIMIT 1",
        (f"PROT-{ano}-%",),
    ).fetchone()
    if ultimo:
        try:
            seq = int(ultimo["numero"].split("-")[-1]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"PROT-{ano}-{seq:04d}"


@bp_protocolos.route("/api/protocolos/proximo-numero", methods=["GET"])
def protocolo_proximo_numero():
    try:
        return jsonify({"numero": _proximo_numero_protocolo(get_db())})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_protocolos.route("/api/protocolos", methods=["GET"])
def protocolos_listar():
    try:
        conn = get_db()
        clauses, params = [], []
        for field in ("tipo", "status", "direcao"):
            val = request.args.get(field, "")
            if val:
                clauses.append(f"{field}=?")
                params.append(val)
        busca = request.args.get("busca", "").strip()
        if busca:
            like = f"%{busca.lower()}%"
            clauses.append(
                "(LOWER(assunto) LIKE ? OR LOWER(origem_destino) LIKE ? OR numero LIKE ?)"
            )
            params.extend([like, like, like])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM protocolos {where} ORDER BY id DESC", params
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_protocolos.route("/api/protocolos", methods=["POST"])
def protocolos_criar():
    try:
        data = request.get_json(force=True) or {}
        assunto = (data.get("assunto") or "").strip()
        tipo = (data.get("tipo") or "").strip()
        data_protocolo = (data.get("data_protocolo") or "").strip()
        if not assunto or not tipo or not data_protocolo:
            return jsonify(
                {"error": "assunto, tipo e data_protocolo são obrigatórios"}
            ), 400
        conn = get_db()
        numero = data.get("numero") or _proximo_numero_protocolo(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO protocolos (numero,tipo,direcao,origem_destino,assunto,data_protocolo,prazo_resposta,status,observacoes) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                numero,
                tipo,
                (data.get("direcao") or "recebido").strip(),
                (data.get("origem_destino") or "").strip(),
                assunto,
                data_protocolo,
                (data.get("prazo_resposta") or "").strip(),
                (data.get("status") or "recebido").strip(),
                (data.get("observacoes") or "").strip(),
            ),
        )
        conn.commit()
        return jsonify(
            dict(
                conn.execute(
                    "SELECT * FROM protocolos WHERE id=?", (cur.lastrowid,)
                ).fetchone()
            )
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_protocolos.route("/api/protocolos/<int:prot_id>", methods=["PUT"])
def protocolos_atualizar(prot_id):
    try:
        data = request.get_json(force=True) or {}
        conn = get_db()
        if not conn.execute(
            "SELECT * FROM protocolos WHERE id=?", (prot_id,)
        ).fetchone():
            return jsonify({"error": "Protocolo não encontrado"}), 404
        fields = {}
        for k in (
            "tipo",
            "direcao",
            "origem_destino",
            "assunto",
            "data_protocolo",
            "prazo_resposta",
            "status",
            "observacoes",
        ):
            if k in data:
                fields[k] = (data[k] or "").strip()
        if not fields:
            return jsonify(
                dict(
                    conn.execute(
                        "SELECT * FROM protocolos WHERE id=?", (prot_id,)
                    ).fetchone()
                )
            )
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(
            f"UPDATE protocolos SET {set_clause} WHERE id=?",
            list(fields.values()) + [prot_id],
        )
        conn.commit()
        return jsonify(
            dict(
                conn.execute(
                    "SELECT * FROM protocolos WHERE id=?", (prot_id,)
                ).fetchone()
            )
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_protocolos.route("/api/protocolos/<int:prot_id>", methods=["DELETE"])
def protocolos_excluir(prot_id):
    try:
        conn = get_db()
        if not conn.execute(
            "SELECT id FROM protocolos WHERE id=?", (prot_id,)
        ).fetchone():
            return jsonify({"error": "Protocolo não encontrado"}), 404
        conn.execute("DELETE FROM protocolos WHERE id=?", (prot_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_protocolos.route("/api/protocolos/<int:prot_id>/anexos", methods=["GET"])
def protocolo_anexos_listar(prot_id):
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT id,protocolo_id,file_name,mime_type,file_size,criado_em FROM protocolo_anexos WHERE protocolo_id=? ORDER BY id",
            (prot_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_protocolos.route("/api/protocolos/<int:prot_id>/anexos", methods=["POST"])
def protocolo_anexos_upload(prot_id):
    try:
        conn = get_db()
        if not conn.execute(
            "SELECT id FROM protocolos WHERE id=?", (prot_id,)
        ).fetchone():
            return jsonify({"error": "Protocolo não encontrado"}), 404
        file = request.files.get("arquivo")
        if not file:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
        content = file.read()
        if not content:
            return jsonify({"error": "Arquivo vazio"}), 400
        if len(content) > 20 * 1024 * 1024:
            return jsonify({"error": "Arquivo excede 20 MB"}), 413
        cur = conn.execute(
            "INSERT INTO protocolo_anexos (protocolo_id,file_name,mime_type,file_size,content) VALUES (?,?,?,?,?)",
            (
                prot_id,
                file.filename,
                file.mimetype or "application/octet-stream",
                len(content),
                content,
            ),
        )
        conn.commit()
        return jsonify(
            dict(
                conn.execute(
                    "SELECT id,protocolo_id,file_name,mime_type,file_size,criado_em FROM protocolo_anexos WHERE id=?",
                    (cur.lastrowid,),
                ).fetchone()
            )
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_protocolos.route(
    "/api/protocolos/<int:prot_id>/anexos/<int:anexo_id>/download", methods=["GET"]
)
def protocolo_anexo_download(prot_id, anexo_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT file_name,mime_type,content FROM protocolo_anexos WHERE id=? AND protocolo_id=?",
            (anexo_id, prot_id),
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


@bp_protocolos.route(
    "/api/protocolos/<int:prot_id>/anexos/<int:anexo_id>", methods=["DELETE"]
)
def protocolo_anexo_excluir(prot_id, anexo_id):
    try:
        conn = get_db()
        if not conn.execute(
            "SELECT id FROM protocolo_anexos WHERE id=? AND protocolo_id=?",
            (anexo_id, prot_id),
        ).fetchone():
            return jsonify({"error": "Anexo não encontrado"}), 404
        conn.execute("DELETE FROM protocolo_anexos WHERE id=?", (anexo_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── RPAs ─────────────────────────────────────────────────────
@bp_rpas.route("/api/rpas", methods=["GET"])
def get_rpas():
    try:
        limit = max(1, min(request.args.get("limit", 100, type=int), 1000))
        offset = max(0, request.args.get("offset", 0, type=int))
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) AS total FROM rpas").fetchone()["total"]
        rows = conn.execute(
            "SELECT * FROM rpas ORDER BY criado_em DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return jsonify(
            {
                "items": [row_to_dict(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_rpas.route("/api/rpas", methods=["POST"])
def create_rpa():
    try:
        data = request.get_json() or {}
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO rpas (numero_rpa,nome_prestador,cpf_prestador,endereco_prestador,descricao_servico,periodo_referencia,carga_horaria,local_execucao,valor_bruto,num_dependentes,pensao_alimenticia,inss,iss,deducao_dependentes,base_calculo_irrf,aliquota_irrf,parcela_deduzir_irrf,ir,valor_liquido,observacoes,data_emissao) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                data.get("numeroRPA"),
                data.get("nomePrestador", ""),
                data.get("cpfPrestador"),
                data.get("enderecoPrestador"),
                data.get("descricaoServico"),
                data.get("periodoReferencia"),
                data.get("cargaHoraria"),
                data.get("localExecucao"),
                data.get("valorBruto", 0),
                data.get("numDependentes", 0),
                data.get("pensaoAlimenticia", 0),
                data.get("inss", 0),
                data.get("iss", 0),
                data.get("deducaoDependentes", 0),
                data.get("baseCalculoIRRF", 0),
                data.get("aliquotaIRRF", 0),
                data.get("parcelaDeduzirIRRF", 0),
                data.get("ir", 0),
                data.get("valorLiquido", 0),
                data.get("observacoes"),
                data.get("dataEmissao"),
            ),
        )
        conn.commit()
        return jsonify(
            row_to_dict(
                conn.execute(
                    "SELECT * FROM rpas WHERE id=?", (cur.lastrowid,)
                ).fetchone()
            )
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_rpas.route("/api/rpas/<int:rpa_id>", methods=["PUT"])
def update_rpa(rpa_id):
    try:
        data = request.get_json() or {}
        conn = get_db()
        conn.execute(
            "UPDATE rpas SET numero_rpa=?,nome_prestador=?,cpf_prestador=?,endereco_prestador=?,descricao_servico=?,periodo_referencia=?,carga_horaria=?,local_execucao=?,valor_bruto=?,num_dependentes=?,pensao_alimenticia=?,inss=?,iss=?,deducao_dependentes=?,base_calculo_irrf=?,aliquota_irrf=?,parcela_deduzir_irrf=?,ir=?,valor_liquido=?,observacoes=?,data_emissao=? WHERE id=?",
            (
                data.get("numeroRPA"),
                data.get("nomePrestador", ""),
                data.get("cpfPrestador"),
                data.get("enderecoPrestador"),
                data.get("descricaoServico"),
                data.get("periodoReferencia"),
                data.get("cargaHoraria"),
                data.get("localExecucao"),
                data.get("valorBruto", 0),
                data.get("numDependentes", 0),
                data.get("pensaoAlimenticia", 0),
                data.get("inss", 0),
                data.get("iss", 0),
                data.get("deducaoDependentes", 0),
                data.get("baseCalculoIRRF", 0),
                data.get("aliquotaIRRF", 0),
                data.get("parcelaDeduzirIRRF", 0),
                data.get("ir", 0),
                data.get("valorLiquido", 0),
                data.get("observacoes"),
                data.get("dataEmissao"),
                rpa_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM rpas WHERE id=?", (rpa_id,)).fetchone()
        if not row:
            return jsonify({"error": "RPA não encontrado"}), 404
        return jsonify(row_to_dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_rpas.route("/api/rpas/<int:rpa_id>", methods=["DELETE"])
def delete_rpa(rpa_id):
    try:
        conn = get_db()
        conn.execute("DELETE FROM rpas WHERE id=?", (rpa_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── FORNECIMENTO ─────────────────────────────────────────────
@bp_fornecimento.route("/api/fornecimento/dados", methods=["GET"])
def get_fornecimento_dados():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT tipo,valor FROM fornecimento_dados ORDER BY valor ASC"
        ).fetchall()
        result = {"solicitantes": [], "empresas": [], "observacoes": []}
        for row in rows:
            if row["tipo"] in result:
                result[row["tipo"]].append(row["valor"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_fornecimento.route("/api/fornecimento/dados", methods=["POST"])
def add_fornecimento_dado():
    try:
        data = request.get_json() or {}
        tipo = (data.get("tipo") or "").strip()
        valor = (data.get("valor") or "").strip()
        if not tipo or not valor:
            return jsonify({"error": "tipo e valor são obrigatórios"}), 400
        conn = get_db()
        conn.execute(
            "INSERT OR IGNORE INTO fornecimento_dados (tipo,valor) VALUES (?,?)",
            (tipo, valor),
        )
        conn.commit()
        return jsonify({"ok": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_fornecimento.route("/api/fornecimento/dados", methods=["DELETE"])
def del_fornecimento_dado():
    try:
        data = request.get_json() or {}
        tipo = (data.get("tipo") or "").strip()
        valor = (data.get("valor") or "").strip()
        if not tipo or not valor:
            return jsonify({"error": "tipo e valor são obrigatórios"}), 400
        conn = get_db()
        conn.execute(
            "DELETE FROM fornecimento_dados WHERE tipo=? AND valor=?", (tipo, valor)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── PDF ──────────────────────────────────────────────────────
@bp_pdf.route("/api/pdf/mesclar", methods=["POST"])
def pdf_mesclar():
    from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter

    files = request.files.getlist("pdfs")
    if len(files) < 2:
        return "Envie ao menos 2 arquivos", 400
    writer = _PdfWriter()
    for f in files:
        for page in _PdfReader(f).pages:
            writer.add_page(page)
    buf = _io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="mesclado.pdf",
    )


@bp_pdf.route("/api/pdf/dividir", methods=["POST"])
def pdf_dividir():
    import zipfile as _zipfile
    from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter

    f = request.files.get("pdf")
    ranges_str = request.form.get("ranges", "").strip()
    if not f or not ranges_str:
        return "Parâmetros inválidos", 400
    reader = _PdfReader(_io.BytesIO(f.read()))
    total = len(reader.pages)
    groups = []
    for part in ranges_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a_i, b_i = max(0, int(a.strip()) - 1), min(total - 1, int(b.strip()) - 1)
            groups.append(
                (f"paginas_{a.strip()}-{b.strip()}.pdf", list(range(a_i, b_i + 1)))
            )
        else:
            p = int(part.strip()) - 1
            if 0 <= p < total:
                groups.append((f"pagina_{part.strip()}.pdf", [p]))
    if not groups:
        return "Nenhuma página válida", 400
    if len(groups) == 1:
        writer = _PdfWriter()
        for p in groups[0][1]:
            writer.add_page(reader.pages[p])
        buf = _io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=groups[0][0],
        )
    zip_buf = _io.BytesIO()
    with _zipfile.ZipFile(zip_buf, "w", _zipfile.ZIP_DEFLATED) as zf:
        for name, pgs in groups:
            writer = _PdfWriter()
            for p in pgs:
                writer.add_page(reader.pages[p])
            pdf_buf = _io.BytesIO()
            writer.write(pdf_buf)
            zf.writestr(name, pdf_buf.getvalue())
    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="dividido.zip",
    )


@bp_pdf.route("/api/pdf/proteger", methods=["POST"])
def pdf_proteger():
    from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter

    f = request.files.get("pdf")
    senha = request.form.get("senha", "")
    if not f or not senha:
        return "Parâmetros inválidos", 400
    writer = _PdfWriter()
    for page in _PdfReader(f).pages:
        writer.add_page(page)
    writer.encrypt(senha)
    buf = _io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="protegido.pdf",
    )


# ── CNPJ ─────────────────────────────────────────────────────
import urllib.request as _urllib_req
import urllib.error as _urllib_err


def _cnpj_so_numeros(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def _cnpj_valido(cnpj: str) -> bool:
    digits = _cnpj_so_numeros(cnpj)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    nums = [int(ch) for ch in digits]
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(nums[i] * pesos1[i] for i in range(12))
    resto1 = soma1 % 11
    dv1 = 0 if resto1 < 2 else 11 - resto1
    if nums[12] != dv1:
        return False
    pesos2 = [6] + pesos1
    soma2 = sum(nums[i] * pesos2[i] for i in range(12)) + dv1 * pesos2[12]
    resto2 = soma2 % 11
    dv2 = 0 if resto2 < 2 else 11 - resto2
    return nums[13] == dv2


def _fmt_moeda(v):
    try:
        return (
            f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
    except Exception:
        return str(v) if v else ""


def _buscar_cnpja(cnpj: str, api_key: str = "") -> dict:
    url = f"https://open.cnpja.com/office/{cnpj}"
    headers = {"User-Agent": "Mozilla/5.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = _urllib_req.Request(url, headers=headers)
    with _urllib_req.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode())
    end = d.get("address", {})
    telefones = [
        f"({p.get('area', '')}) {p.get('number', '')} [{p.get('type', '')}]"
        for p in d.get("phones", [])
        if p.get("number")
    ]
    emails = [
        f"{e.get('address', '')} [{e.get('ownership', '')}]"
        for e in d.get("emails", [])
        if e.get("address")
    ]
    socios = [
        {
            "nome": m.get("person", {}).get("name", ""),
            "qualificacao": m.get("role", {}).get("text", ""),
        }
        for m in d.get("company", {}).get("members", [])
    ]
    cnaes_sec = [a.get("text", "") for a in d.get("sideActivities", [])]
    complemento = end.get("details", "")
    end_str = f"{end.get('street', '')} {end.get('number', '')}".strip()
    if complemento:
        end_str += f", {complemento}"
    end_str += f" - {end.get('district', '')} - {end.get('city', '')}/{end.get('state', '')} - CEP {end.get('zip', '')}"
    return {
        "cnpj": cnpj,
        "razao_social": d.get("company", {}).get("name", ""),
        "nome_fantasia": d.get("alias", ""),
        "situacao": d.get("status", {}).get("text", ""),
        "situacao_id": d.get("status", {}).get("id", ""),
        "data_situacao": d.get("statusDate", ""),
        "data_abertura": d.get("founded", ""),
        "natureza_juridica": d.get("company", {}).get("nature", {}).get("text", ""),
        "capital_social": _fmt_moeda(d.get("company", {}).get("equity")),
        "porte": d.get("company", {}).get("size", {}).get("text", ""),
        "simples": "Sim"
        if d.get("company", {}).get("simples", {}).get("optant")
        else "Não",
        "mei": "Sim" if d.get("company", {}).get("simei", {}).get("optant") else "Não",
        "matriz": "Sim" if d.get("head") else "Filial",
        "endereco": end_str,
        "cnae_principal": d.get("mainActivity", {}).get("text", ""),
        "cnaes_secundarios": cnaes_sec,
        "socios": socios,
        "telefones": telefones,
        "emails": emails,
        "fonte": "CNPJá",
    }


def _buscar_receitaws(cnpj: str) -> dict:
    url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj}"
    req = _urllib_req.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _urllib_req.urlopen(req, timeout=10) as r:
        d = json.loads(r.read().decode())
    if d.get("status") == "ERROR":
        raise Exception(d.get("message", "CNPJ não encontrado"))
    socios = [
        {"nome": s.get("nome", ""), "qualificacao": s.get("qual", "")}
        for s in d.get("qsa", [])
    ]
    return {
        "cnpj": cnpj,
        "razao_social": d.get("nome", ""),
        "nome_fantasia": d.get("fantasia", ""),
        "situacao": d.get("situacao", ""),
        "situacao_id": (d.get("situacao") or "").upper(),
        "data_abertura": d.get("abertura", ""),
        "natureza_juridica": d.get("natureza_juridica", ""),
        "capital_social": d.get("capital_social", ""),
        "porte": d.get("porte", ""),
        "simples": d.get("simples", ""),
        "mei": d.get("mei", ""),
        "endereco": f"{d.get('logradouro', '')} {d.get('numero', '')}".strip(),
        "cnae_principal": d.get("atividade_principal", [{}])[0].get("text", "")
        if d.get("atividade_principal")
        else "",
        "cnaes_secundarios": [
            a.get("text", "") for a in d.get("atividades_secundarias", [])
        ],
        "socios": socios,
        "telefones": [d.get("telefone", "")] if d.get("telefone") else [],
        "emails": [d.get("email", "")] if d.get("email") else [],
        "fonte": "ReceitaWS",
    }


@bp_cnpj.route("/api/cnpj/buscar", methods=["POST"])
def cnpj_buscar():
    d = request.get_json()
    cnpj = _cnpj_so_numeros(d.get("cnpj", ""))
    api_key = d.get("api_key_cnpja", "").strip()
    if len(cnpj) != 14:
        return jsonify({"error": "CNPJ deve ter 14 dígitos"}), 400
    if not _cnpj_valido(cnpj):
        return jsonify({"error": "CNPJ inválido"}), 400
    try:
        return jsonify(_buscar_cnpja(cnpj, api_key))
    except _urllib_err.HTTPError as e:
        if e.code == 429:
            return jsonify(
                {"error": "Limite de consultas atingido (5/min). Aguarde 1 minuto."}
            ), 429
    except Exception:
        pass
    try:
        return jsonify(_buscar_receitaws(cnpj))
    except Exception as e2:
        return jsonify({"error": f"CNPJ não encontrado: {e2}"}), 404


# ── IA Chat Proxy ────────────────────────────────────────────
@bp_ia.route("/api/ia/chat", methods=["POST"])
def proxy_ia_chat():
    from services.openrouter_service import AIServiceError

    try:
        data = request.get_json(force=True) or {}
        conn = get_db()
        api_key, model = _get_openrouter_config(
            conn,
            api_key_override=(data.get("api_key") or "").strip(),
            model_override=(data.get("model") or "").strip(),
        )
        if not api_key:
            return jsonify({"error": "Chave API OpenRouter não configurada."}), 400
        response = _build_ai_service(api_key, model).chat_by_task(
            task_type="chat",
            messages=data.get("messages", []),
            temperature=data.get("temperature", 0.2),
            max_tokens=data.get("max_tokens", 2000),
            use_cache=bool(data.get("use_cache", False)),
            response_format=data.get("response_format"),
            stream=bool(data.get("stream", False)),
            metadata={"feature": "proxy_ia_chat"},
        )
        return jsonify(response.payload)
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── CONFIG ───────────────────────────────────────────────────
ALLOWED_CONFIG_KEYS = {
    "api_openrouter_key",
    "api_openrouter_modelo",
    "api_cnpja_key",
    "api_autentique_key",
    "api_tavily_key",
}


@bp_config.route("/api/config", methods=["GET"])
def config_get():
    try:
        conn = get_db()
        rows = conn.execute("SELECT chave,valor FROM configuracoes").fetchall()
        return jsonify(
            {r["chave"]: r["valor"] for r in rows if r["chave"] in ALLOWED_CONFIG_KEYS}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_config.route("/api/config", methods=["POST"])
def config_set():
    d = request.get_json(force=True)
    try:
        conn = get_db()
        for chave, valor in d.items():
            if chave in ALLOWED_CONFIG_KEYS:
                conn.execute(
                    "INSERT INTO configuracoes (chave,valor,atualizado_em) VALUES (?,?,datetime('now','localtime')) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor,atualizado_em=excluded.atualizado_em",
                    (chave, str(valor)),
                )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_config.route("/api/admin/summary", methods=["GET"])
def admin_summary():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT chave,valor,atualizado_em FROM configuracoes WHERE chave IN (?,?,?,?)",
            (
                "api_openrouter_key",
                "api_openrouter_modelo",
                "api_cnpja_key",
                "api_autentique_key",
            ),
        ).fetchall()
        cfg = {row["chave"]: row_to_dict(row) for row in rows}

        def _parse_aut_keys(value: str) -> list[str]:
            text = (value or "").replace("\r", "\n")
            raw_items = []
            for chunk in text.split("\n"):
                raw_items.extend(part.strip() for part in chunk.split(","))
            keys = [item for item in raw_items if item]
            seen = set()
            unique = []
            for item in keys:
                if item in seen:
                    continue
                seen.add(item)
                unique.append(item)
            return unique

        return jsonify(
            {
                "overview": {
                    "credores_ativos": conn.execute(
                        "SELECT COUNT(*) AS total FROM credores WHERE ativo=1"
                    ).fetchone()["total"],
                    "rpas_total": conn.execute(
                        "SELECT COUNT(*) AS total FROM rpas"
                    ).fetchone()["total"],
                    "kanban_total": conn.execute(
                        "SELECT COUNT(*) AS total FROM kanban_tasks"
                    ).fetchone()["total"],
                    "importacoes_total": conn.execute(
                        "SELECT COUNT(*) AS total FROM empenhos_importacoes"
                    ).fetchone()["total"],
                    "logs_total": conn.execute(
                        "SELECT COUNT(*) AS total FROM logs"
                    ).fetchone()["total"],
                },
                "health": {
                    "status": "ok",
                    "db": True,
                    "uptime_s": 0,
                    "cache_files": 0,
                    "cache_gzip": 0,
                },
                "config_status": {
                    "openrouter_key_configured": bool(
                        cfg.get("api_openrouter_key", {}).get("valor", "").strip()
                    ),
                    "openrouter_model": cfg.get("api_openrouter_modelo", {}).get(
                        "valor", settings.openrouter_default_model
                    )
                    or settings.openrouter_default_model,
                    "openrouter_updated_at": cfg.get("api_openrouter_key", {}).get(
                        "atualizado_em"
                    )
                    or cfg.get("api_openrouter_modelo", {}).get("atualizado_em"),
                    "cnpja_key_configured": bool(
                        cfg.get("api_cnpja_key", {}).get("valor", "").strip()
                    ),
                    "cnpja_updated_at": cfg.get("api_cnpja_key", {}).get(
                        "atualizado_em"
                    ),
                    "autentique_key_configured": bool(
                        _parse_aut_keys(
                            cfg.get("api_autentique_key", {}).get("valor", "")
                        )
                    ),
                    "autentique_key_count": len(
                        _parse_aut_keys(
                            cfg.get("api_autentique_key", {}).get("valor", "")
                        )
                    ),
                    "autentique_updated_at": cfg.get("api_autentique_key", {}).get(
                        "atualizado_em"
                    ),
                },
                "recent_logs": [
                    row_to_dict(row)
                    for row in conn.execute(
                        "SELECT id,acao,credor_id,credor_nome,detalhes,data FROM logs ORDER BY data DESC LIMIT 8"
                    ).fetchall()
                ],
                "technical": {
                    "host": settings.host,
                    "port": settings.port,
                    "debug": settings.debug,
                    "db_path": str(settings.db_path),
                    "log_file": str(settings.log_file),
                    "base_dir": str(settings.base_dir),
                },
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── LOGS ─────────────────────────────────────────────────────
@bp_logs.route("/api/logs", methods=["GET"])
def get_logs():
    try:
        conn = get_db()
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))
        acao = (request.args.get("acao") or "").strip()
        if acao:
            total = conn.execute(
                "SELECT COUNT(*) FROM logs WHERE acao=?", (acao,)
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT id,acao,credor_id,credor_nome,detalhes,data FROM logs WHERE acao=? ORDER BY data DESC LIMIT ? OFFSET ?",
                (acao, limit, offset),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
            rows = conn.execute(
                "SELECT id,acao,credor_id,credor_nome,detalhes,data FROM logs ORDER BY data DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return jsonify({"logs": [row_to_dict(r) for r in rows], "total": total})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── AUTH ─────────────────────────────────────────────────────
_ADM_HASH = ""


def init_auth_hash(admin_password: str):
    global _ADM_HASH
    _ADM_HASH = (
        hashlib.sha256(admin_password.encode()).hexdigest() if admin_password else ""
    )


@bp_auth.route("/api/auth/adm", methods=["POST"])
def auth_adm():
    from routes.helpers import rate_limited

    if not _ADM_HASH:
        return jsonify(
            {"ok": False, "error": "Senha administrativa não configurada."}
        ), 503
    ip = request.remote_addr or "unknown"
    if rate_limited(f"auth:{ip}", max_hits=5, window=60):
        return jsonify(
            {"ok": False, "error": "Muitas tentativas. Aguarde 1 minuto."}
        ), 429
    d = request.get_json(force=True) or {}
    if hashlib.sha256(d.get("senha", "").encode()).hexdigest() == _ADM_HASH:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Senha incorreta"}), 401


@bp_auth.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True})


@bp_auth.route("/api/health", methods=["GET"])
def health():
    try:
        get_db().execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({"status": "ok" if db_ok else "degraded", "db": db_ok})


# ── EXTRATOS ─────────────────────────────────────────────────
@bp_extratos.route("/api/extratos/modelos-openrouter", methods=["GET", "POST"])
def extratos_modelos_openrouter():
    from services.openrouter_service import AIServiceError, listar_modelos

    try:
        data = request.get_json(silent=True) or {}
        conn = get_db()
        api_key, selected_model = _get_openrouter_config(
            conn,
            api_key_override=(
                data.get("api_key") or request.args.get("api_key") or ""
            ).strip(),
            model_override=(
                data.get("model") or request.args.get("model") or ""
            ).strip(),
        )
        if not api_key:
            return jsonify(
                {
                    "error": "Chave do OpenRouter não configurada.",
                    "modelos": [],
                    "models": [],
                    "selected_model": selected_model,
                }
            ), 400
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
            pricing = model.get("pricing") or {}
            if (
                str(pricing.get("prompt") or "").strip() != "0"
                or str(pricing.get("completion") or "").strip() != "0"
            ):
                continue
            normalized.append(
                {
                    "id": (model.get("id") or "").strip(),
                    "name": (model.get("name") or model.get("id") or "").strip(),
                    "context_length": model.get("context_length"),
                    "pricing": pricing,
                }
            )
        return jsonify(
            {
                "modelos": normalized,
                "models": normalized,
                "selected_model": selected_model,
            }
        )
    except AIServiceError as err:
        return jsonify(
            {"error": err.user_message, "modelos": [], "models": []}
        ), err.status_code
    except Exception as e:
        return jsonify({"error": str(e), "modelos": [], "models": []}), 500


# ── EMPENHO ASSISTENTE ───────────────────────────────────────
def _clean_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_empenho_payload(payload: dict) -> dict:
    data = dict(payload or {})
    return {
        k: _clean_value(data.get(k))
        for k in (
            "secretaria",
            "fornecedor",
            "tipo_despesa",
            "finalidade",
            "valor",
            "competencia",
            "processo",
            "pregao",
            "contrato",
            "nota_fiscal",
            "texto_base",
            "descricao_atual",
            "observacoes",
            "fonte",
            "arquivo_nome",
            "arquivo_tipo",
        )
    }


def _serialize_json(value):
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "{}"
        try:
            json.loads(text)
            return text
        except Exception:
            return json.dumps({"texto": text}, ensure_ascii=False)
    if value is None:
        return "{}"
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"texto": str(value)}, ensure_ascii=False)


def _extract_text_from_result(result):
    if isinstance(result, dict):
        return _serialize_json(result)
    if hasattr(result, "content"):
        return result.content or ""
    return str(result) if result else ""


def _save_empenho_assistente_history(
    conn, action: str, payload: dict, result, meta: dict | None = None
) -> int:
    from services.ai_tasks import serialize_task_result

    meta = meta or {}
    extracted, checklist, descricao_base, descricao_melhorada, diff = {}, {}, "", "", {}
    if action == "extract_fields" and isinstance(result, dict):
        extracted = result
    elif action == "checklist" and isinstance(result, dict):
        checklist = result
    elif action == "generate_description":
        descricao_base = _extract_text_from_result(result)
    elif action == "improve_description":
        descricao_melhorada = _extract_text_from_result(result)
    elif action == "review_bundle" and isinstance(result, dict):
        extracted = (
            result.get("campos") if isinstance(result.get("campos"), dict) else {}
        )
        checklist = (
            result.get("checklist") if isinstance(result.get("checklist"), dict) else {}
        )
        descricao_base = _clean_value(result.get("descricao_base"))
        descricao_melhorada = _clean_value(result.get("descricao_melhorada"))
        diff = result.get("diff") if isinstance(result.get("diff"), dict) else {}
    result_payload = (
        serialize_task_result(result) if not isinstance(result, dict) else result
    )
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO empenho_assistente_historico (action,payload_json,resultado_json,campos_json,checklist_json,descricao_base,descricao_melhorada,diff_json,model,cached) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            action,
            _serialize_json(payload),
            _serialize_json(result_payload),
            _serialize_json(extracted),
            _serialize_json(checklist),
            descricao_base,
            descricao_melhorada,
            _serialize_json(diff),
            _clean_value(meta.get("model")),
            1 if meta.get("cached") else 0,
        ),
    )
    conn.commit()
    return cur.lastrowid


@bp_empenho_assistente.route("/api/empenho-assistente", methods=["POST"])
def empenho_assistente():
    from services.openrouter_service import AIServiceError

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()
    payload = _normalize_empenho_payload(data.get("payload") or {})
    conn = get_db()
    api_key, model = _get_openrouter_config(conn)
    if not api_key:
        return jsonify({"error": "Chave do OpenRouter não configurada."}), 400
    if action not in {
        "extract_fields",
        "generate_description",
        "checklist",
        "improve_description",
        "review_bundle",
    }:
        return jsonify({"error": "Ação inválida."}), 400
    try:
        facade = _build_ai_facade(api_key, model)
        result = facade.gerar_texto_empenho(payload, acao=action)
        meta = {"model": model, "cached": False, "usage": {}}
        if hasattr(result, "model"):
            meta = {
                "model": result.model,
                "cached": result.cached,
                "usage": result.usage,
            }
        history_id = _save_empenho_assistente_history(
            conn, action, payload, result, meta=meta
        )
        if isinstance(result, dict):
            return jsonify(
                {
                    "action": action,
                    "resultado": result,
                    "history_id": history_id,
                    "meta": meta,
                }
            )
        return jsonify(
            {
                "action": action,
                "resultado": result.content,
                "history_id": history_id,
                "meta": meta,
            }
        )
    except ValueError as err:
        return jsonify({"error": str(err)}), 400
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_empenho_assistente.route("/api/empenho-assistente/historico", methods=["GET"])
def empenho_assistente_historico():
    try:
        conn = get_db()
        try:
            limit = min(max(int(request.args.get("limit", 12) or 12), 1), 50)
        except (TypeError, ValueError):
            limit = 12
        rows = conn.execute(
            "SELECT id,action,payload_json,resultado_json,campos_json,checklist_json,descricao_base,descricao_melhorada,diff_json,model,cached,criado_em FROM empenho_assistente_historico ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "action": row["action"],
                    "payload": json.loads(row["payload_json"] or "{}"),
                    "resultado": json.loads(row["resultado_json"] or "{}"),
                    "campos": json.loads(row["campos_json"] or "{}"),
                    "checklist": json.loads(row["checklist_json"] or "{}"),
                    "descricao_base": row["descricao_base"] or "",
                    "descricao_melhorada": row["descricao_melhorada"] or "",
                    "diff": json.loads(row["diff_json"] or "{}"),
                    "model": row["model"] or "",
                    "cached": bool(row["cached"]),
                    "criado_em": row["criado_em"],
                }
            )
        return jsonify({"items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── CLASSIFICADOR DE DESPESA ────────────────────────────────
@bp_classificador.route("/api/classificador-despesa", methods=["POST"])
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
                        json.dumps(result, ensure_ascii=False),
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


@bp_classificador.route("/api/classificador-despesa/historico", methods=["GET"])
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


@bp_classificador.route(
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


@bp_classificador.route("/api/classificador-despesa/historico", methods=["DELETE"])
def classificador_historico_limpar():
    try:
        conn = get_db()
        conn.execute("DELETE FROM classificador_despesa_historico")
        conn.commit()
        return jsonify({"ok": True, "cleared": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── DESPESAS (CSV Import) ────────────────────────────────────
@bp_despesas.route("/api/despesas/importacoes", methods=["GET"])
def despesas_listar_importacoes():
    conn = get_db()
    rows = conn.execute(
        "SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM despesas_importacoes ORDER BY importado_em DESC"
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@bp_despesas.route("/api/despesas/importar", methods=["POST"])
def despesas_importar():
    try:
        d = request.get_json(force=True)
        if not d:
            return jsonify({"error": "JSON inválido"}), 400
        periodo = (d.get("periodo") or "").strip()
        linhas = d.get("linhas", [])
        if not periodo:
            return jsonify({"error": "Período obrigatório"}), 400
        if not linhas:
            return jsonify({"error": "Nenhuma linha recebida"}), 400
        from datetime import datetime as _dt_now

        now = _dt_now.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO despesas_importacoes (periodo,descricao,arquivo,total_rows,colunas,importado_em) VALUES (?,?,?,?,?,?)",
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
            "INSERT INTO despesas_linhas (importacao_id,dados) VALUES (?,?)",
            [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas],
        )
        conn.commit()
        return jsonify(
            row_to_dict(
                conn.execute(
                    "SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM despesas_importacoes WHERE id=?",
                    (imp_id,),
                ).fetchone()
            )
        ), 201
    except Exception as e:
        return jsonify({"error": "Erro ao salvar", "detail": str(e)}), 500


@bp_despesas.route("/api/despesas/importacoes/<int:imp_id>", methods=["GET"])
def despesas_carregar(imp_id):
    conn = get_db()
    imp = conn.execute(
        "SELECT id,periodo,descricao,arquivo,total_rows,colunas,importado_em FROM despesas_importacoes WHERE id=?",
        (imp_id,),
    ).fetchone()
    if not imp:
        return jsonify({"error": "Importação não encontrada"}), 404
    linhas = [
        json.loads(r["dados"])
        for r in conn.execute(
            "SELECT dados FROM despesas_linhas WHERE importacao_id=? ORDER BY id",
            (imp_id,),
        ).fetchall()
    ]
    imp_dict = row_to_dict(imp)
    imp_dict["colunas"] = json.loads(imp_dict["colunas"] or "[]")
    return jsonify({"importacao": imp_dict, "linhas": linhas})


@bp_despesas.route("/api/despesas/importacoes/<int:imp_id>", methods=["DELETE"])
def despesas_excluir(imp_id):
    conn = get_db()
    conn.execute("DELETE FROM despesas_linhas WHERE importacao_id=?", (imp_id,))
    conn.execute("DELETE FROM despesas_importacoes WHERE id=?", (imp_id,))
    conn.commit()
    return jsonify({"ok": True})


@bp_despesas.route("/api/despesas/importacoes/<int:imp_id>/resumo", methods=["GET"])
def despesas_resumo(imp_id):
    conn = get_db()
    imp = conn.execute(
        "SELECT id,periodo,descricao,arquivo,total_rows,colunas,importado_em FROM despesas_importacoes WHERE id=?",
        (imp_id,),
    ).fetchone()
    if not imp:
        return jsonify({"error": "Importação não encontrada"}), 404
    colunas = json.loads(imp["colunas"] or "[]")
    linhas = [
        json.loads(r["dados"])
        for r in conn.execute(
            "SELECT dados FROM despesas_linhas WHERE importacao_id=?", (imp_id,)
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


# ── DESPESAS IA ──────────────────────────────────────────────
@bp_despesas.route("/api/despesas/ia", methods=["POST"])
def despesas_ia():
    from services.openrouter_service import AIServiceError
    import datetime

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


# ── EMPENHOS CSV ─────────────────────────────────────────────
@bp_despesas.route("/api/empenhos-csv/importar", methods=["POST"])
def empenhos_csv_importar():
    try:
        d = request.get_json(force=True)
        if not d:
            return jsonify({"error": "JSON inválido"}), 400
        periodo = (d.get("periodo") or "").strip()
        linhas = d.get("linhas", [])
        if not periodo or not linhas:
            return jsonify({"error": "Período e linhas obrigatórios"}), 400
        from datetime import datetime as _dt

        now = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO empenhos_importacoes (periodo,descricao,arquivo,total_rows,importado_em) VALUES (?,?,?,?,?)",
            (
                periodo,
                (d.get("descricao") or "").strip(),
                (d.get("arquivo") or "").strip(),
                len(linhas),
                now,
            ),
        )
        imp_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO empenhos_linhas (importacao_id,dados) VALUES (?,?)",
            [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas],
        )
        conn.commit()
        return jsonify(
            row_to_dict(
                conn.execute(
                    "SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM empenhos_importacoes WHERE id=?",
                    (imp_id,),
                ).fetchone()
            )
        ), 201
    except Exception as e:
        return jsonify({"error": "Erro ao salvar", "detail": str(e)}), 500


@bp_despesas.route("/api/empenhos-csv/importacoes", methods=["GET"])
def empenhos_csv_listar():
    conn = get_db()
    rows = conn.execute(
        "SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM empenhos_importacoes ORDER BY importado_em DESC"
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@bp_despesas.route("/api/empenhos-csv/importacoes/<int:imp_id>", methods=["GET"])
def empenhos_csv_carregar(imp_id):
    conn = get_db()
    imp = conn.execute(
        "SELECT id,periodo,descricao,arquivo,total_rows,importado_em FROM empenhos_importacoes WHERE id=?",
        (imp_id,),
    ).fetchone()
    if not imp:
        return jsonify({"error": "Importação não encontrada"}), 404
    linhas = [
        json.loads(r["dados"])
        for r in conn.execute(
            "SELECT dados FROM empenhos_linhas WHERE importacao_id=? ORDER BY id",
            (imp_id,),
        ).fetchall()
    ]
    return jsonify({"importacao": row_to_dict(imp), "linhas": linhas})


@bp_despesas.route("/api/empenhos-csv/importacoes/<int:imp_id>", methods=["DELETE"])
def empenhos_csv_excluir(imp_id):
    conn = get_db()
    conn.execute("DELETE FROM empenhos_linhas WHERE importacao_id=?", (imp_id,))
    conn.execute("DELETE FROM empenhos_importacoes WHERE id=?", (imp_id,))
    conn.commit()
    return jsonify({"ok": True})
