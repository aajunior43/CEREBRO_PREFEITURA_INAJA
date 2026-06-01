"""Blueprint: Gerador de PDF LaTeX com IA."""

import io
import os
import re
import shutil
import subprocess
import uuid

from flask import Blueprint, jsonify, request, send_file

from config import settings
from routes._shared import _build_ai_service, _get_openrouter_config, get_db, require_login

bp = Blueprint("latex_pdf", __name__)


LATEX_SYSTEM_PROMPT = """
Voce e um assistente especializado em documentos oficiais em LaTeX para prefeitura.
Gere somente o codigo LaTeX final, sem markdown, sem cercas de codigo e sem explicacoes.
Use um documento completo e compilavel. Prefira pacotes comuns:
\\documentclass[12pt,a4paper]{article}
\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage{geometry}
\\usepackage{longtable}
\\usepackage{array}
\\usepackage{xcolor}
\\geometry{margin=2.5cm}
Evite \\write18, \\input, \\include, \\openout e comandos que dependam de arquivos externos.
Nao use pacotes LaTeX fora desta lista: inputenc, fontenc, geometry, longtable, array, xcolor.
Nao use pdfscape, lscape, tikz, pgfplots, fancyhdr, titlesec, enumitem, booktabs, graphicx, hyperref ou pacotes que possam exigir instalacao adicional.
O texto deve ser formal, claro e adequado a documento administrativo publico.
""".strip()


FORBIDDEN_LATEX_PATTERNS = (
    r"\\write18\b",
    r"\\input\b",
    r"\\include\b",
    r"\\openout\b",
    r"\\read\b",
    r"\\usepackage\s*\{shellesc\}",
)

BLOCKED_PACKAGES = {
    "pdfscape",
    "lscape",
    "tikz",
    "pgfplots",
    "fancyhdr",
    "titlesec",
    "enumitem",
    "booktabs",
    "graphicx",
    "hyperref",
}


def _strip_code_fences(text: str) -> str:
    text = (text or "").strip()
    match = re.search(r"```(?:latex|tex)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _validate_latex_source(source: str):
    if not source or len(source.strip()) < 80:
        return "O codigo LaTeX esta vazio ou incompleto."
    if "\\documentclass" not in source or "\\begin{document}" not in source or "\\end{document}" not in source:
        return "A IA nao retornou um documento LaTeX completo."
    for pattern in FORBIDDEN_LATEX_PATTERNS:
        if re.search(pattern, source, re.IGNORECASE):
            return "O codigo contem comandos LaTeX bloqueados por seguranca."
    return None


def _normalize_latex_source(source: str) -> str:
    source = re.sub(r"\\usepackage\s*\[\s*(?:brazil|brazilian|portuguese)\s*\]\s*\{babel\}\s*", "", source, flags=re.IGNORECASE)
    for package in BLOCKED_PACKAGES:
        source = re.sub(
            rf"\\usepackage(?:\[[^\]]*\])?\s*\{{{re.escape(package)}\}}\s*",
            "",
            source,
            flags=re.IGNORECASE,
        )
    source = re.sub(r"\\begin\{landscape\}", "", source, flags=re.IGNORECASE)
    source = re.sub(r"\\end\{landscape\}", "", source, flags=re.IGNORECASE)
    source = re.sub(r"\\begin\{sidewaysfigure\}.*?\\end\{sidewaysfigure\}", "", source, flags=re.IGNORECASE | re.DOTALL)
    return source


def _latex_engine():
    for executable in ("pdflatex", "xelatex", "lualatex"):
        path = shutil.which(executable)
        if path:
            return path
    local_appdata = os.environ.get("LOCALAPPDATA") or ""
    program_files = os.environ.get("ProgramFiles") or r"C:\Program Files"
    candidates = []
    for base in (local_appdata, program_files):
        if base:
            candidates.extend(
                os.path.join(base, "Programs", "MiKTeX", "miktex", "bin", "x64", name)
                for name in ("pdflatex.exe", "xelatex.exe", "lualatex.exe")
            )
            candidates.extend(
                os.path.join(base, "MiKTeX", "miktex", "bin", "x64", name)
                for name in ("pdflatex.exe", "xelatex.exe", "lualatex.exe")
            )
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


@bp.route("/api/latex-pdf/gerar", methods=["POST"])
@require_login
def gerar_latex_com_ia():
    from services.openrouter_service import AIServiceError

    try:
        data = request.get_json(force=True) or {}
        prompt = (data.get("prompt") or "").strip()
        tipo = (data.get("tipo") or "documento oficial").strip()
        estilo = (data.get("estilo") or "formal").strip()
        detalhes = (data.get("detalhes") or "").strip()
        if not prompt:
            return jsonify({"error": "Informe o conteudo ou objetivo do documento."}), 400

        conn = get_db()
        api_key, model = _get_openrouter_config(conn)
        if not api_key:
            return jsonify({"error": "Chave de IA nao configurada. Configure em ADM."}), 400

        user_prompt = f"""
Tipo de documento: {tipo}
Estilo: {estilo}
Pedido principal:
{prompt}

Dados e observacoes adicionais:
{detalhes or "Nenhum."}

Crie o documento LaTeX completo, pronto para compilar em PDF.
""".strip()

        response = _build_ai_service(api_key, model).chat_by_task(
            task_type="chat",
            messages=[
                {"role": "system", "content": LATEX_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=3500,
            use_cache=False,
            metadata={"feature": "latex_pdf_generator"},
        )
        latex = _normalize_latex_source(_strip_code_fences(response.text))
        error = _validate_latex_source(latex)
        if error:
            return jsonify({"error": error, "latex": latex}), 502
        return jsonify({"latex": latex, "model": response.model, "usage": response.usage})
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/latex-pdf/status", methods=["GET"])
def status_latex():
    engine = _latex_engine()
    if engine:
        name = os.path.basename(engine).replace(".exe", "")
        return jsonify({"available": True, "engine": name, "path": engine})
    return jsonify({"available": False})


@bp.route("/api/latex-pdf/refinar", methods=["POST"])
@require_login
def refinar_latex_com_ia():
    from services.openrouter_service import AIServiceError

    try:
        data = request.get_json(force=True) or {}
        latex = _strip_code_fences(data.get("latex") or "")
        instrucoes = (data.get("instrucoes") or "").strip()
        if not latex or not instrucoes:
            return jsonify({"error": "Informe o codigo LaTeX e as instrucoes de refinamento."}), 400

        conn = get_db()
        api_key, model = _get_openrouter_config(conn)
        if not api_key:
            return jsonify({"error": "Chave de IA nao configurada. Configure em ADM."}), 400

        user_prompt = f"""Codigo LaTeX atual:
{latex}

Instrucoes de refinamento:
{instrucoes}

Retorne apenas o codigo LaTeX completo e corrigido, sem explicacoes nem cerca de codigo.""".strip()

        response = _build_ai_service(api_key, model).chat_by_task(
            task_type="chat",
            messages=[
                {"role": "system", "content": LATEX_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=3500,
            use_cache=False,
            metadata={"feature": "latex_pdf_refine"},
        )
        refined = _normalize_latex_source(_strip_code_fences(response.text))
        error = _validate_latex_source(refined)
        if error:
            return jsonify({"error": error, "latex": refined}), 502
        return jsonify({"latex": refined, "model": response.model, "usage": response.usage})
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/latex-pdf/sugerir-opcoes", methods=["POST"])
@require_login
def sugerir_opcoes_latex():
    """Gera perguntas de multipla escolha para campos faltantes antes de gerar LaTeX."""
    data = request.get_json(force=True) or {}
    tipo = (data.get("tipo") or "documento oficial").strip()
    estilo = (data.get("estilo") or "formal").strip()
    prompt = (data.get("prompt") or "").strip()
    detalhes = (data.get("detalhes") or "").strip()
    missing_fields = data.get("missing_fields") or []

    if isinstance(missing_fields, str):
        try:
            import json as _json_local
            missing_fields = _json_local.loads(missing_fields)
        except Exception:
            missing_fields = [m.strip() for m in missing_fields.split(",") if m.strip()]

    if not prompt:
        return jsonify({"error": "Prompt e obrigatorio para gerar sugestoes."}), 400

    conn = get_db()
    api_key, model = _get_openrouter_config(conn)
    if not api_key:
        return jsonify({"error": "Chave do OpenRouter nao configurada."}), 400

    try:
        svc = _build_ai_service(api_key, model)
        from services.ai_prompts import build_prompt as _build_ai_prompt

        dados_preenchidos = []
        if tipo:
            dados_preenchidos.append(f"Tipo: {tipo}")
        if estilo:
            dados_preenchidos.append(f"Estilo: {estilo}")
        if detalhes:
            dados_preenchidos.append(f"Dados adicionais: {detalhes}")

        campos_pendentes = "\n".join(f"- {m}" for m in missing_fields) if missing_fields else "(todos preenchidos)"

        messages = _build_ai_prompt(
            "latex_suggest_options",
            tipo=tipo,
            estilo=estilo,
            prompt=prompt[:4000],
            dados_preenchidos="\n".join(dados_preenchidos) if dados_preenchidos else "(nenhum)",
            campos_pendentes=campos_pendentes,
        )

        resp = svc.chat_by_task(
            task_type="chat",
            messages=messages,
            temperature=0.25,
            max_tokens=1500,
            use_cache=False,
            metadata={"feature": "latex_suggest_options"},
        )

        text = (resp.content or "").strip()
        text = text.replace("**", "").replace("*", "")

        from services.openrouter_service import extract_json_block as _extract_json

        parsed = _extract_json(text)
        if isinstance(parsed, dict):
            default = {"inferidos": {}, "perguntas": []}
            default.update(parsed)
            if not isinstance(default.get("inferidos"), dict):
                default["inferidos"] = {}
            if not isinstance(default.get("perguntas"), list):
                default["perguntas"] = []
            for i, p in enumerate(default["perguntas"]):
                if not isinstance(p, dict):
                    default["perguntas"][i] = {"campo": "", "pergunta": "", "opcoes": [], "inferida": ""}
                if not isinstance(p.get("opcoes"), list):
                    p["opcoes"] = []
            return jsonify({
                "inferidos": default["inferidos"],
                "perguntas": default["perguntas"],
                "model": resp.model,
            })

        return jsonify({"inferidos": {}, "perguntas": [], "model": resp.model})
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp.route("/api/latex-pdf/compilar", methods=["POST"])
@require_login
def compilar_latex_pdf():
    data = request.get_json(force=True) or {}
    source = _normalize_latex_source(_strip_code_fences(data.get("latex") or ""))
    filename = re.sub(r"[^a-zA-Z0-9_-]+", "_", (data.get("filename") or "documento_latex").strip()).strip("_")
    filename = filename[:80] or "documento_latex"

    error = _validate_latex_source(source)
    if error:
        return jsonify({"error": error}), 400

    engine = _latex_engine()
    if not engine:
        return jsonify({
            "error": "Nenhum compilador LaTeX encontrado. Instale MiKTeX ou TeX Live para gerar o PDF diretamente.",
            "code": "latex_engine_missing",
        }), 501

    temp_root = os.path.join(settings.base_dir, "tmp", "latex_pdf")
    miktex_root = os.path.join(os.path.expanduser("~"), ".codex", "memories", "miktex_latex_pdf")
    os.makedirs(temp_root, exist_ok=True)
    os.makedirs(os.path.join(miktex_root, "config"), exist_ok=True)
    os.makedirs(os.path.join(miktex_root, "data"), exist_ok=True)
    os.makedirs(os.path.join(miktex_root, "cache"), exist_ok=True)

    tmpdir = os.path.join(temp_root, f"job_{uuid.uuid4().hex}")
    os.makedirs(tmpdir, exist_ok=False)
    try:
        tex_path = os.path.join(tmpdir, "documento.tex")
        pdf_path = os.path.join(tmpdir, "documento.pdf")
        with open(tex_path, "w", encoding="utf-8") as tex_file:
            tex_file.write(source)

        cmd = [
            engine,
            "--disable-installer",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-no-shell-escape",
            "documento.tex",
        ]
        last_output = ""
        env = os.environ.copy()
        env.update(
            {
                "MIKTEX_USERCONFIG": os.path.join(miktex_root, "config"),
                "MIKTEX_USERDATA": os.path.join(miktex_root, "data"),
                "MIKTEX_USERCACHE": os.path.join(miktex_root, "cache"),
                "MIKTEX_AUTO_INSTALL": "0",
            }
        )
        for _ in range(2):
            proc = subprocess.run(
                cmd,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45,
                env=env,
            )
            last_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            if proc.returncode != 0:
                tail = "\n".join(last_output.splitlines()[-45:])
                return jsonify({"error": "Falha ao compilar o LaTeX.", "log": tail}), 400

        if not os.path.exists(pdf_path):
            return jsonify({"error": "O compilador terminou sem gerar PDF."}), 500

        with open(pdf_path, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{filename}.pdf",
    )
