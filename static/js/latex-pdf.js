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
    refineWrap: $("latex-refine-wrap"),
    refine: $("latex-refine"),
    compilerBadge: $("latex-compiler-status"),
    countPrompt: $("count-prompt"),
    countDetalhes: $("count-detalhes"),
  };

  const STORAGE_KEY = "latex_pdf_state";

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        tipo: els.tipo.value,
        filename: els.filename.value,
        estilo: els.estilo.value,
        prompt: els.prompt.value,
        detalhes: els.detalhes.value,
        source: els.source.value,
      }));
    } catch (_) {}
  }

  function restoreState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      const state = JSON.parse(raw);
      if (state.tipo) els.tipo.value = state.tipo;
      if (state.filename) els.filename.value = state.filename;
      if (state.estilo) els.estilo.value = state.estilo;
      if (state.prompt != null) els.prompt.value = state.prompt;
      if (state.detalhes != null) els.detalhes.value = state.detalhes;
      if (state.source != null) els.source.value = state.source;
      return !!(state.prompt || state.source);
    } catch (_) { return false; }
  }

  function clearState() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
  }

  [els.tipo, els.filename, els.estilo, els.prompt, els.detalhes, els.source].forEach((el) => {
    el.addEventListener("input", saveState);
    el.addEventListener("change", saveState);
  });

  // Contadores de caracteres
  function updateCharCount(textarea, counterEl, warnAt) {
    const len = textarea.value.length;
    counterEl.textContent = `${len.toLocaleString("pt-BR")} caractere${len !== 1 ? "s" : ""}`;
    counterEl.classList.toggle("warn", warnAt > 0 && len > warnAt);
  }

  els.prompt.addEventListener("input", () => updateCharCount(els.prompt, els.countPrompt, 1500));
  els.detalhes.addEventListener("input", () => updateCharCount(els.detalhes, els.countDetalhes, 1000));

  // Indicador de compilador LaTeX
  async function checkCompilerStatus() {
    if (!els.compilerBadge) return;
    try {
      const res = await fetch("/api/latex-pdf/status");
      const data = await res.json().catch(() => ({}));
      els.compilerBadge.className = "latex-compiler-badge";
      if (data.available) {
        els.compilerBadge.classList.add("latex-compiler-ok");
        els.compilerBadge.textContent = data.engine || "LaTeX disponivel";
        els.compilerBadge.title = `Compilador encontrado: ${data.path || data.engine}`;
      } else {
        els.compilerBadge.classList.add("latex-compiler-missing");
        els.compilerBadge.textContent = "Sem compilador";
        els.compilerBadge.title = "Nenhum compilador LaTeX encontrado. Instale MiKTeX ou TeX Live para gerar PDFs.";
      }
    } catch (_) {
      els.compilerBadge.className = "latex-compiler-badge latex-compiler-missing";
      els.compilerBadge.textContent = "Sem compilador";
    }
  }

  checkCompilerStatus();

  const PREAMBLE = String.raw`\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{geometry}
\usepackage{longtable}
\usepackage{array}
\usepackage{xcolor}
\geometry{margin=2.5cm}`;

  const TEMPLATES = {
    "Oficio": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.3cm]
\end{center}

\noindent\textbf{Of\'icio N\textordmasculine\ \_\_\_/2024}\\
\noindent\textbf{Inaj\'a, \today.}

\vspace{0.6cm}
\noindent\textbf{A(o) Senhor(a)}\\
\noindent [Nome do Destinat\'ario]\\
\noindent [Cargo / \'Org\~ao]\\
\noindent [Endere\c{c}o]

\vspace{0.6cm}
\noindent\textbf{Assunto:} [Descreva o assunto resumidamente.]

\vspace{0.6cm}
\noindent Senhor(a) [Tratamento],

\vspace{0.4cm}
\noindent [Texto principal do of\'icio. Descreva a solicita\c{c}\~ao, informa\c{c}\~ao ou comunica\c{c}\~ao de forma clara e objetiva.]

\vspace{1cm}
\noindent Atenciosamente,

\vspace{1.5cm}
\begin{center}
\rule{8cm}{0.4pt}\\
[Nome do Signat\'ario]\\
[Cargo]\\
Prefeitura Municipal de Inaj\'a
\end{center}

\end{document}
`,

    "Memorando": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.3cm]
{\large \textbf{MEMORANDO INTERNO}}
\end{center}

\vspace{0.5cm}
\noindent\textbf{Memorando N\textordmasculine\ \_\_\_/2024}\\
\noindent\textbf{De:} [Secretaria / Setor de Origem]\\
\noindent\textbf{Para:} [Secretaria / Setor Destinat\'ario]\\
\noindent\textbf{Data:} \today\\
\noindent\textbf{Assunto:} [Assunto do memorando]

\vspace{0.8cm}
\noindent [Texto do memorando. Seja direto e objetivo, comunicando a informa\c{c}\~ao ou solicita\c{c}\~ao interna de forma clara.]

\vspace{1.5cm}
\begin{flushright}
[Nome do Remetente]\\
[Cargo]
\end{flushright}

\end{document}
`,

    "Relatorio": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.4cm]
{\large \textbf{RELAT\'ORIO}}\\[0.2cm]
{\normalsize [T\'itulo do Relat\'orio]}
\end{center}

\vspace{0.5cm}
\noindent\textbf{Secretaria:} [Nome da Secretaria]\\
\noindent\textbf{Per\'iodo:} [Per\'iodo de refer\^encia]\\
\noindent\textbf{Respons\'avel:} [Nome do Respons\'avel]\\
\noindent\textbf{Data:} \today

\section*{1. Introdu\c{c}\~ao}
[Descreva o objetivo e contexto do relat\'orio.]

\section*{2. Desenvolvimento}
[Apresente os dados, an\'alises ou atividades realizadas.]

\section*{3. Resultados}
[Liste os resultados obtidos.]

\section*{4. Considera\c{c}\~oes Finais}
[Conclus\~oes e recomenda\c{c}\~oes.]

\vspace{1.5cm}
\begin{center}
\rule{8cm}{0.4pt}\\
[Nome do Respons\'avel]\\
[Cargo]
\end{center}

\end{document}
`,

    "Declaracao": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.4cm]
{\large \textbf{DECLARA\c{C}\~AO}}
\end{center}

\vspace{1cm}
\noindent Declaro, para os devidos fins, que [Nome Completo], portador(a) do CPF n\textordmasculine\ [CPF], residente \`a [Endere\c{c}o], [descreva o objeto da declara\c{c}\~ao].

\vspace{0.6cm}
\noindent Por ser verdade, firmo a presente declara\c{c}\~ao.

\vspace{1.5cm}
\begin{flushright}
Inaj\'a, \today.
\end{flushright}

\vspace{2cm}
\begin{center}
\rule{8cm}{0.4pt}\\
[Nome do Declarante]\\
[Cargo / Fun\c{c}\~ao]\\
Prefeitura Municipal de Inaj\'a
\end{center}

\end{document}
`,

    "Termo de referencia": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.4cm]
{\large \textbf{TERMO DE REFER\^ENCIA}}\\[0.2cm]
{\normalsize Processo n\textordmasculine\ \_\_\_\_\_\_\_\_\_\_}
\end{center}

\section*{1. Objeto}
[Descreva o objeto da contrata\c{c}\~ao ou aquisi\c{c}\~ao.]

\section*{2. Justificativa}
[Justifique a necessidade da contrata\c{c}\~ao.]

\section*{3. Especifica\c{c}\~oes T\'ecnicas}

\begin{longtable}{|>{\centering}p{0.5cm}|p{6cm}|>{\centering}p{1.5cm}|>{\centering}p{2cm}|>{\centering\arraybackslash}p{2cm}|}
\hline
\textbf{It.} & \textbf{Descri\c{c}\~ao} & \textbf{Unid.} & \textbf{Qtd.} & \textbf{Valor Unit.} \\
\hline
1 & [Descri\c{c}\~ao do item] & [Un] & [Qtd] & R\$ [Valor] \\
\hline
\end{longtable}

\section*{4. Prazo de Entrega / Execu\c{c}\~ao}
[Informe o prazo.]

\section*{5. Dotação Orçamentária}
[Informe a dotação orçamentária.]

\vspace{1.5cm}
\begin{center}
\rule{8cm}{0.4pt}\\
[Nome do Respons\'avel]\\
[Secretaria]
\end{center}

\end{document}
`,

    "Ata": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.4cm]
{\large \textbf{ATA DE REUNI\~AO}}\\[0.2cm]
{\normalsize N\textordmasculine\ \_\_\_/2024}
\end{center}

\vspace{0.5cm}
\noindent Aos [dia] dias do m\^es de [m\^es] de [ano], \`as [hora], reuniram-se na [local da reuni\~ao], os seguintes presentes:

\vspace{0.3cm}
\noindent\textbf{Presentes:}
\begin{itemize}
  \item [Nome] -- [Cargo]
  \item [Nome] -- [Cargo]
\end{itemize}

\vspace{0.3cm}
\noindent\textbf{Pauta:} [Descreva os pontos da pauta.]

\vspace{0.3cm}
\noindent\textbf{Delibera\c{c}\~oes:}

\noindent [Registre as discuss\~oes e decis\~oes tomadas na reuni\~ao.]

\vspace{0.5cm}
\noindent Nada mais havendo a tratar, lavrou-se a presente ata que, lida e aprovada, vai assinada pelos presentes.

\vspace{1.5cm}
\begin{flushright}
Inaj\'a, \today.
\end{flushright}

\vspace{1.5cm}
\begin{center}
\rule{7cm}{0.4pt}\quad\rule{7cm}{0.4pt}\\[0.1cm]
[Participante 1]\hspace{4.5cm}[Participante 2]
\end{center}

\end{document}
`,

    "Contrato": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.4cm]
{\large \textbf{CONTRATO N\textordmasculine\ \_\_\_/2024}}\\[0.2cm]
{\normalsize Processo Licit\'atorio n\textordmasculine\ \_\_\_\_\_\_\_\_\_\_}
\end{center}

\vspace{0.5cm}
\noindent\textbf{CONTRATANTE:} Prefeitura Municipal de Inaj\'a, pessoa jur\'idica de direito p\'ublico interno, CNPJ n\textordmasculine\ [CNPJ], com sede \`a [Endere\c{c}o], neste ato representada pelo Prefeito Municipal, [Nome do Prefeito].

\vspace{0.3cm}
\noindent\textbf{CONTRATADA:} [Nome da Empresa], pessoa jur\'idica de direito privado, CNPJ n\textordmasculine\ [CNPJ], com sede \`a [Endere\c{c}o], representada por [Nome do Representante].

\section*{Cl\'ausula 1\textordfeminine\ -- Do Objeto}
[Descreva o objeto do contrato.]

\section*{Cl\'ausula 2\textordfeminine\ -- Do Valor}
O valor total do presente contrato \'e de R\$ [Valor] ([Valor por extenso]).

\section*{Cl\'ausula 3\textordfeminine\ -- Do Prazo}
O prazo de vig\^encia \'e de [prazo], contado a partir da data de assinatura.

\section*{Cl\'ausula 4\textordfeminine\ -- Da Dotação Orçamentária}
[Dotação orçamentária.]

\section*{Cl\'ausula 5\textordfeminine\ -- Das Obriga\c{c}\~oes}
[Obrigações das partes.]

\section*{Cl\'ausula 6\textordfeminine\ -- Do Foro}
Fica eleito o foro da Comarca de [Cidade] para dirimir quaisquer d\'uvidas.

\vspace{1cm}
\noindent Inaj\'a, \today.

\vspace{2cm}
\begin{center}
\rule{7cm}{0.4pt}\quad\rule{7cm}{0.4pt}\\[0.1cm]
CONTRATANTE\hspace{5.5cm}CONTRATADA
\end{center}

\end{document}
`,

    "Portaria": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.4cm]
{\large \textbf{PORTARIA N\textordmasculine\ \_\_\_/2024}}
\end{center}

\vspace{0.5cm}
\noindent O Prefeito Municipal de Inaj\'a, Estado de Pernambuco, no uso das atribui\c{c}\~oes que lhe s\~ao conferidas pela Lei Org\^anica Municipal, e

\vspace{0.3cm}
\noindent\textbf{Considerando} [fundamento legal ou motivo];

\vspace{0.3cm}
\noindent\textbf{RESOLVE:}

\vspace{0.3cm}
\noindent\textbf{Art. 1\textordmasculine} [Conte\'udo do artigo.]

\noindent\textbf{Art. 2\textordmasculine} [Conte\'udo do artigo.]

\noindent\textbf{Art. 3\textordmasculine} Esta Portaria entra em vigor na data de sua publica\c{c}\~ao.

\vspace{1.5cm}
\begin{flushright}
Gabinete do Prefeito, Inaj\'a, \today.
\end{flushright}

\vspace{2cm}
\begin{center}
\rule{8cm}{0.4pt}\\
[Nome do Prefeito]\\
Prefeito Municipal de Inaj\'a
\end{center}

\end{document}
`,

    "Decreto": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.4cm]
{\large \textbf{DECRETO N\textordmasculine\ \_\_\_/2024}}
\end{center}

\vspace{0.5cm}
\noindent O Prefeito Municipal de Inaj\'a, Estado de Pernambuco, no uso das atribui\c{c}\~oes que lhe s\~ao conferidas pelo art.\ [artigo] da Lei Org\^anica Municipal,

\vspace{0.3cm}
\noindent\textbf{DECRETA:}

\vspace{0.3cm}
\noindent\textbf{Art. 1\textordmasculine} [Objeto do decreto.]

\noindent\textbf{Art. 2\textordmasculine} [Complemento.]

\noindent\textbf{Art. 3\textordmasculine} [Responsabilidade pela execu\c{c}\~ao.]

\noindent\textbf{Art. 4\textordmasculine} Este Decreto entra em vigor na data de sua publica\c{c}\~ao, revogadas as disposi\c{c}\~oes em contr\'ario.

\vspace{1.5cm}
\begin{flushright}
Gabinete do Prefeito, Inaj\'a, \today.
\end{flushright}

\vspace{2cm}
\begin{center}
\rule{8cm}{0.4pt}\\
[Nome do Prefeito]\\
Prefeito Municipal de Inaj\'a
\end{center}

\end{document}
`,

    "Edital": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.1cm]
{\normalsize Estado de Pernambuco}\\[0.4cm]
{\large \textbf{EDITAL N\textordmasculine\ \_\_\_/2024}}\\[0.1cm]
{\normalsize [Modalidade de Licita\c{c}\~ao] -- [Objeto Resumido]}
\end{center}

\vspace{0.3cm}
\noindent A Prefeitura Municipal de Inaj\'a, CNPJ n\textordmasculine\ [CNPJ], por meio da Comiss\~ao de Licita\c{c}\~ao, torna p\'ublico que realizar\'a licita\c{c}\~ao na modalidade \textbf{[Modalidade]}, tipo \textbf{[Tipo]}, nos termos da Lei Federal n\textordmasculine\ 14.133/2021.

\section*{1. Do Objeto}
[Objeto detalhado da licita\c{c}\~ao.]

\section*{2. Das Condi\c{c}\~oes de Participa\c{c}\~ao}
[Requisitos para participa\c{c}\~ao.]

\section*{3. Do Recebimento das Propostas}
\noindent\textbf{Data:} [Data]\\
\noindent\textbf{Hora:} [Hora]\\
\noindent\textbf{Local:} [Local]

\section*{4. Do Valor Estimado}
R\$ [Valor] ([Valor por extenso]).

\section*{5. Da Dotação Orçamentária}
[Dotação orçamentária.]

\section*{6. Das Informa\c{c}\~oes Adicionais}
O Edital completo est\'a dispon\'ivel na sede da Prefeitura Municipal de Inaj\'a.

\vspace{1cm}
\begin{flushright}
Inaj\'a, \today.
\end{flushright}

\vspace{1.5cm}
\begin{center}
\rule{8cm}{0.4pt}\\
Presidente da Comiss\~ao de Licita\c{c}\~ao
\end{center}

\end{document}
`,

    "Documento oficial": String.raw`${PREAMBLE}

\begin{document}

\begin{center}
{\Large \textbf{PREFEITURA MUNICIPAL DE INAJA}}\\[0.2cm]
{\large \textbf{DOCUMENTO OFICIAL}}\\[0.4cm]
\end{center}

\section*{Assunto}
Descreva aqui o assunto do documento.

\section*{Conte\'udo}
Digite aqui o texto principal.

\vspace{1.5cm}
\begin{flushright}
Inaj\'a, \today.
\end{flushright}

\vspace{2cm}
\begin{center}
\rule{8cm}{0.4pt}\\
Assinatura
\end{center}

\end{document}
`,
  };

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

  // #4 — parse "l.42" line-number hints from pdflatex log
  function parseErrorLines(log) {
    const found = [];
    const re = /\bl\.(\d+)\b/g;
    let m;
    while ((m = re.exec(log)) !== null) {
      const n = parseInt(m[1], 10);
      if (n > 0) found.push(n);
    }
    return [...new Set(found)].sort((a, b) => a - b);
  }

  function goToLine(lineNum) {
    const ta = els.source;
    const lines = ta.value.split("\n");
    let pos = 0;
    for (let i = 0; i < Math.min(lineNum - 1, lines.length); i++) pos += lines[i].length + 1;
    ta.focus();
    ta.setSelectionRange(pos, pos + (lines[lineNum - 1] ? lines[lineNum - 1].length : 0));
    const lh = parseFloat(getComputedStyle(ta).lineHeight) || 20;
    ta.scrollTop = Math.max(0, (lineNum - 5) * lh);
  }

  function showErrorWithLines(message, lineNumbers) {
    els.status.style.display = "none";
    els.status.textContent = "";
    els.error.style.display = "block";
    els.error.textContent = message;
    if (lineNumbers.length > 0) {
      const wrap = document.createElement("div");
      wrap.className = "latex-err-lines";
      lineNumbers.forEach((ln) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "latex-err-line-btn";
        btn.textContent = `Ir para linha ${ln}`;
        btn.addEventListener("click", () => goToLine(ln));
        wrap.appendChild(btn);
      });
      els.error.appendChild(wrap);
    }
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
      saveState();
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
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const msg = data.log
          ? `${data.error || "Falha ao compilar."}\n\n${data.log}`
          : (data.error || `HTTP ${response.status}`);
        showErrorWithLines(msg, data.log ? parseErrorLines(data.log) : []);
        return;
      }
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

  // #3 — Refinar com IA
  async function refinarLatex() {
    const instrucoes = els.refine.value.trim();
    clearMessages();
    if (!els.source.value.trim()) { showError("Nao ha codigo LaTeX para refinar."); return; }
    if (!instrucoes) { showError("Descreva o que deseja alterar ou corrigir."); return; }
    setBusy(true);
    showStatus("Refinando LaTeX com IA...");
    try {
      const response = await fetch("/api/latex-pdf/refinar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ latex: els.source.value, instrucoes }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      els.source.value = data.latex || "";
      saveState();
      showStatus("LaTeX refinado com sucesso. Revise antes de compilar.");
    } catch (err) {
      showError(err instanceof Error ? err.message : "Erro ao refinar LaTeX.");
    } finally {
      setBusy(false);
    }
  }

  // #5 — Pré-preencher dados da prefeitura
  const DADOS_PREFEITURA = [
    "Prefeitura Municipal de Inaja",
    "Estado de Pernambuco",
    "CNPJ: [CNPJ da Prefeitura]",
    "Endereco: Rua [Logradouro], s/n, Centro, Inaja - PE, CEP [CEP]",
    "Telefone: (87) [Telefone]",
    "Prefeito: [Nome do Prefeito]",
    "Secretaria: [Nome da Secretaria]",
    "Responsavel: [Nome do Responsavel]",
    "Cargo: [Cargo do Responsavel]",
    `Ano: ${new Date().getFullYear()}`,
  ].join("\n");

  function preencherDadosPrefeitura() {
    const atual = els.detalhes.value.trim();
    els.detalhes.value = atual ? `${DADOS_PREFEITURA}\n\n${atual}` : DADOS_PREFEITURA;
    saveState();
    showStatus("Dados da Prefeitura inseridos em Dados adicionais. Edite os campos entre colchetes.");
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
  $("btn-aplicar-refine").addEventListener("click", refinarLatex);
  $("btn-dados-prefeitura").addEventListener("click", preencherDadosPrefeitura);
  $("btn-toggle-refine").addEventListener("click", () => {
    const isOpen = els.refineWrap.classList.toggle("open");
    $("btn-toggle-refine").textContent = isOpen ? "Fechar refinamento" : "Refinar com IA";
    if (isOpen) els.refine.focus();
  });
  $("btn-cancelar-refine").addEventListener("click", () => {
    els.refineWrap.classList.remove("open");
    $("btn-toggle-refine").textContent = "Refinar com IA";
  });
  $("btn-limpar-codigo").addEventListener("click", () => {
    els.source.value = "";
    els.preview.innerHTML = '<div class="latex-preview-empty">Depois de compilar, uma pre-visualizacao do PDF aparece aqui.</div>';
    clearMessages();
    saveState();
  });
  $("btn-modelo").addEventListener("click", () => {
    const tipo = els.tipo.value;
    els.source.value = TEMPLATES[tipo] || TEMPLATES["Documento oficial"];
    saveState();
    showStatus(`Modelo de ${tipo} inserido no editor.`);
  });
  $("btn-limpar").addEventListener("click", () => {
    els.prompt.value = "";
    els.detalhes.value = "";
    els.source.value = "";
    els.preview.innerHTML = '<div class="latex-preview-empty">Depois de compilar, uma pre-visualizacao do PDF aparece aqui.</div>';
    clearMessages();
    clearState();
  });

  const restored = restoreState();
  if (!els.source.value.trim()) els.source.value = TEMPLATES["Documento oficial"];
  updateCharCount(els.prompt, els.countPrompt, 1500);
  updateCharCount(els.detalhes, els.countDetalhes, 1000);
  if (restored) showStatus("Rascunho restaurado automaticamente.");
})();
