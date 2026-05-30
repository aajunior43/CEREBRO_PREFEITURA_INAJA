(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const els = {
    tipo: $("latex-tipo"),
    filename: $("latex-filename"),
    estilo: $("latex-estilo"),
    prompt: $("latex-prompt"),
    detalhes: $("latex-detalhes"),
    source: $("latex-source"),
    status: $("latex-status"),
    error: $("latex-error"),
    preview: $("latex-preview"),
  };

  const defaultTemplate = String.raw`\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{geometry}
\usepackage{longtable}
\usepackage{array}
\usepackage{xcolor}
\geometry{margin=2.5cm}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.2cm]
{\large \textbf{DOCUMENTO OFICIAL}}\\[0.4cm]
\end{center}

\section*{Assunto}
Descreva aqui o assunto do documento.

\section*{Conteudo}
Digite aqui o texto principal.

\vspace{1.5cm}
\begin{flushright}
Inaja, \today.
\end{flushright}

\vspace{2cm}
\begin{center}
\rule{8cm}{0.4pt}\\
Assinatura
\end{center}

\end{document}
`;

  function setBusy(isBusy) {
    document.querySelectorAll(".latex-btn").forEach((btn) => {
      btn.disabled = isBusy;
    });
  }

  function showStatus(message) {
    els.error.style.display = "none";
    els.error.textContent = "";
    els.status.style.display = "block";
    els.status.textContent = message;
  }

  function showError(message) {
    els.status.style.display = "none";
    els.status.textContent = "";
    els.error.style.display = "block";
    els.error.textContent = message;
  }

  function clearMessages() {
    els.status.style.display = "none";
    els.error.style.display = "none";
    els.status.textContent = "";
    els.error.textContent = "";
  }

  function cleanFilename() {
    return (els.filename.value || "documento_latex").replace(/[^a-zA-Z0-9_-]+/g, "_").replace(/^_+|_+$/g, "") || "documento_latex";
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 800);
    return url;
  }

  async function parseError(response) {
    const data = await response.json().catch(() => ({}));
    if (data.log) return `${data.error || "Erro"}\n\n${data.log}`;
    if (data.error && typeof data.error === "object") return data.error.message || JSON.stringify(data.error);
    return data.error || `HTTP ${response.status}`;
  }

  async function gerarLatex() {
    clearMessages();
    if (!els.prompt.value.trim()) {
      showError("Informe o conteudo desejado antes de gerar.");
      return;
    }
    setBusy(true);
    showStatus("Gerando codigo LaTeX com IA...");
    try {
      const response = await fetch("/api/latex-pdf/gerar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tipo: els.tipo.value,
          estilo: els.estilo.value,
          prompt: els.prompt.value,
          detalhes: els.detalhes.value,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      els.source.value = data.latex || "";
      showStatus("LaTeX gerado. Revise o codigo antes de compilar.");
    } catch (err) {
      showError(err instanceof Error ? err.message : "Erro ao gerar LaTeX.");
    } finally {
      setBusy(false);
    }
  }

  async function compilarPdf() {
    clearMessages();
    if (!els.source.value.trim()) {
      showError("Nao ha codigo LaTeX para compilar.");
      return;
    }
    setBusy(true);
    showStatus("Compilando PDF...");
    try {
      const response = await fetch("/api/latex-pdf/compilar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ latex: els.source.value, filename: cleanFilename() }),
      });
      if (!response.ok) throw new Error(await parseError(response));
      const blob = await response.blob();
      const filename = `${cleanFilename()}.pdf`;
      const url = downloadBlob(blob, filename);
      els.preview.innerHTML = "";
      const iframe = document.createElement("iframe");
      iframe.title = "Pre-visualizacao do PDF";
      iframe.src = url;
      els.preview.appendChild(iframe);
      showStatus("PDF compilado e baixado com sucesso.");
    } catch (err) {
      showError(err instanceof Error ? err.message : "Erro ao compilar PDF.");
    } finally {
      setBusy(false);
    }
  }

  function baixarTex() {
    clearMessages();
    const latex = els.source.value.trim();
    if (!latex) {
      showError("Nao ha codigo LaTeX para baixar.");
      return;
    }
    downloadBlob(new Blob([latex], { type: "text/x-tex;charset=utf-8" }), `${cleanFilename()}.tex`);
    showStatus("Arquivo .tex preparado para download.");
  }

  async function copiarCodigo() {
    clearMessages();
    if (!els.source.value.trim()) {
      showError("Nao ha codigo para copiar.");
      return;
    }
    try {
      await navigator.clipboard.writeText(els.source.value);
      showStatus("Codigo copiado para a area de transferencia.");
    } catch (_err) {
      showError("Nao foi possivel copiar automaticamente.");
    }
  }

  $("btn-gerar-latex").addEventListener("click", gerarLatex);
  $("btn-compilar").addEventListener("click", compilarPdf);
  $("btn-baixar-tex").addEventListener("click", baixarTex);
  $("btn-copiar").addEventListener("click", copiarCodigo);
  $("btn-modelo").addEventListener("click", () => {
    els.source.value = defaultTemplate;
    showStatus("Modelo LaTeX inserido no editor.");
  });
  $("btn-limpar").addEventListener("click", () => {
    els.prompt.value = "";
    els.detalhes.value = "";
    els.source.value = "";
    els.preview.innerHTML = '<div class="latex-preview-empty">Depois de compilar, uma pre-visualizacao do PDF aparece aqui.</div>';
    clearMessages();
  });

  if (!els.source.value.trim()) els.source.value = defaultTemplate;
})();
