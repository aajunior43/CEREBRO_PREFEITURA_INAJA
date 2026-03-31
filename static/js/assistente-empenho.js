window.__ASSISTENTE_EMPENHO_CUSTOM__ = true;

(function () {
  'use strict';

  const pdfLib = window.pdfjsLib;
  if (pdfLib?.GlobalWorkerOptions) {
    pdfLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js';
  }

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
  const clean = value => String(value ?? '').trim();

  const fields = {
    secretaria: $('secretaria'),
    fornecedor: $('fornecedor'),
    tipo_despesa: $('tipo_despesa'),
    finalidade: $('finalidade'),
    valor: $('valor'),
    competencia: $('competencia'),
    processo: $('processo'),
    pregao: $('pregao'),
    contrato: $('contrato'),
    nota_fiscal: $('nota_fiscal'),
    fonte: $('fonte'),
    observacoes: $('observacoes'),
    texto_base: $('texto_base'),
    descricao_resultado: $('descricao_resultado'),
  };

  const fileInput = $('arquivo_documento');
  const dropzone = $('ea-upload-dropzone') || $('ea-dropzone');
  const uploadTitle = $('ea-upload-title');
  const fileRow = $('ea-file-row');
  const fileName = $('ea-file-name');
  const fileMeta = $('ea-file-meta');
  const loader = $('ea-loader');
  const errorBox = $('ea-error');
  const statusBox = $('ea-status');
  const painelCampos = $('painel_campos');
  const painelChecklist = $('painel_checklist');
  const painelDiff = $('painel_diff');
  const historicoLista = $('historico_lista');

  let currentFile = null;
  let currentHistory = [];

  function setBusy(isBusy) {
    loader.style.display = isBusy ? 'flex' : 'none';
    document.querySelectorAll('.ea-btn').forEach(btn => {
      if (btn.id === 'btn-copy' || btn.id === 'btn-download') return;
      btn.disabled = isBusy;
    });
  }

  function showError(message) {
    statusBox.style.display = 'none';
    statusBox.textContent = '';
    errorBox.style.display = 'block';
    errorBox.textContent = message;
  }

  function showStatus(message) {
    errorBox.style.display = 'none';
    errorBox.textContent = '';
    statusBox.style.display = 'block';
    statusBox.textContent = message;
  }

  function hideMessages() {
    errorBox.style.display = 'none';
    errorBox.textContent = '';
    statusBox.style.display = 'none';
    statusBox.textContent = '';
  }

  function setFile(file) {
    currentFile = file || null;
    if (!currentFile) {
      fileInput.value = '';
      fileRow.style.display = 'none';
      uploadTitle.textContent = 'Clique ou arraste um arquivo';
      return;
    }
    fileName.textContent = currentFile.name;
    fileMeta.textContent = `${currentFile.type || 'arquivo'} • ${formatSize(currentFile.size)}`;
    fileRow.style.display = 'flex';
    uploadTitle.textContent = 'Arquivo selecionado';
  }

  function formatSize(size) {
    if (!Number.isFinite(size)) return '';
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(2)} MB`;
  }

  function payloadFromForm() {
    return {
      secretaria: clean(fields.secretaria.value),
      fornecedor: clean(fields.fornecedor.value),
      tipo_despesa: clean(fields.tipo_despesa.value),
      finalidade: clean(fields.finalidade.value),
      valor: clean(fields.valor.value),
      competencia: clean(fields.competencia.value),
      processo: clean(fields.processo.value),
      pregao: clean(fields.pregao.value),
      contrato: clean(fields.contrato.value),
      nota_fiscal: clean(fields.nota_fiscal.value),
      fonte: clean(fields.fonte.value),
      observacoes: clean(fields.observacoes.value),
      texto_base: clean(fields.texto_base.value),
      descricao_atual: clean(fields.descricao_resultado.value),
      arquivo_nome: currentFile?.name || '',
      arquivo_tipo: currentFile?.type || '',
    };
  }

  function renderExtraction(data) {
    const entries = [
      ['secretaria', data.secretaria],
      ['fornecedor', data.fornecedor],
      ['tipo_despesa', data.tipo_despesa],
      ['finalidade', data.finalidade],
      ['valor', data.valor],
      ['competencia', data.competencia],
      ['processo', data.processo],
      ['pregao', data.pregao],
      ['contrato', data.contrato],
      ['nota_fiscal', data.nota_fiscal],
      ['observacoes', data.observacoes],
    ].filter(([, value]) => clean(value) !== '');

    if (!entries.length && !(Array.isArray(data.pendencias) && data.pendencias.length)) {
      painelCampos.innerHTML = '<div class="ea-mini-item"><strong>Nenhuma extracao ainda.</strong></div>';
      return;
    }

    painelCampos.innerHTML = entries.map(([key, value]) => `
      <div class="ea-mini-item">
        <strong>${key.replace(/_/g, ' ')}</strong>
        <p>${esc(value)}</p>
      </div>
    `).join('');

    if (Array.isArray(data.pendencias) && data.pendencias.length) {
      painelCampos.insertAdjacentHTML('beforeend',
        data.pendencias.map(item => `<div class="ea-mini-item"><strong>Pendencia</strong><p>${esc(item)}</p></div>`).join(''));
    }
  }

  function renderChecklist(data) {
    const itens = Array.isArray(data?.itens) ? data.itens : [];
    const pendencias = Array.isArray(data?.pendencias) ? data.pendencias : [];
    const html = [];
    if (clean(data?.resumo)) {
      html.push(`<div class="ea-mini-item"><strong>Resumo</strong><p>${esc(data.resumo)}</p></div>`);
    }
    if (clean(data?.prioridade)) {
      html.push(`<div class="ea-mini-item"><strong>Prioridade</strong><p>${esc(data.prioridade)}</p></div>`);
    }
    itens.forEach(item => html.push(`<div class="ea-mini-item"><strong>Item</strong><p>${esc(item)}</p></div>`));
    pendencias.forEach(item => html.push(`<div class="ea-mini-item"><strong>Pendencia</strong><p>${esc(item)}</p></div>`));
    painelChecklist.innerHTML = html.length ? html.join('') : '<div class="ea-mini-item"><strong>Checklist ainda nao gerado.</strong></div>';
  }

  function renderDiff(diff, beforeText, afterText) {
    const before = clean(beforeText);
    const after = clean(afterText);
    const first = diff?.first_change || {};
    painelDiff.innerHTML = `
      <div class="ea-mini-item">
        <strong>Resumo</strong>
        <p>${esc(diff?.summary || 'Comparacao concluida.')}</p>
      </div>
      <div class="ea-mini-item">
        <strong>Tamanho</strong>
        <p>${before.length} caracteres antes / ${after.length} depois</p>
      </div>
      <div class="ea-mini-item">
        <strong>Trecho original</strong>
        <p>${esc(first.before || diff?.before_excerpt || before).slice(0, 260)}</p>
      </div>
      <div class="ea-mini-item">
        <strong>Trecho revisado</strong>
        <p>${esc(first.after || diff?.after_excerpt || after).slice(0, 260)}</p>
      </div>
    `;
  }

  function renderHistory(items) {
    currentHistory = Array.isArray(items) ? items : [];
    if (!currentHistory.length) {
      historicoLista.innerHTML = '<div class="ea-mini-item"><strong>Nenhum historico registrado ainda.</strong></div>';
      return;
    }
    historicoLista.innerHTML = currentHistory.map(item => `
      <div class="ea-mini-item">
        <strong>${esc({
          extract_fields: 'Extracao de campos',
          generate_description: 'Descricao gerada',
          checklist: 'Checklist',
          improve_description: 'Descricao revisada',
          review_bundle: 'Revisao completa',
        }[item.action] || item.action)}</strong>
        <p>${esc(item.criado_em || '')}</p>
        <p>${esc(item.action === 'review_bundle'
          ? 'Bundle com extracao, checklist e comparacao.'
          : item.action === 'extract_fields'
            ? 'Campos extraidos do documento.'
            : item.action === 'checklist'
              ? 'Checklist de pendencias.'
              : item.action === 'improve_description'
                ? 'Versao revisada da descricao.'
                : 'Descricao produzida a partir do contexto.')}</p>
        <button class="ea-btn" type="button" data-history-id="${item.id}" style="margin-top:10px;">Carregar</button>
      </div>
    `).join('');

    historicoLista.querySelectorAll('[data-history-id]').forEach(btn => {
      btn.addEventListener('click', () => {
        const item = currentHistory.find(row => String(row.id) === String(btn.dataset.historyId));
        if (item) hydrateFromHistory(item);
      });
    });
  }

  function hydrateFromHistory(item) {
    const payload = item.payload || {};
    Object.keys(fields).forEach(key => {
      if (fields[key] && key in payload) fields[key].value = payload[key] || '';
    });
    if (item.resultado?.content) {
      fields.descricao_resultado.value = item.resultado.content;
    } else if (item.descricao_melhorada) {
      fields.descricao_resultado.value = item.descricao_melhorada;
    } else if (item.descricao_base) {
      fields.descricao_resultado.value = item.descricao_base;
    }
    if (item.campos) renderExtraction(item.campos);
    if (item.checklist) renderChecklist(item.checklist);
    if (item.diff) renderDiff(item.diff, item.descricao_base, item.descricao_melhorada || item.descricao_base);
    showStatus('Historico carregado na tela.');
  }

  async function loadHistory() {
    try {
      const response = await fetch('/api/empenho-assistente/historico?limit=10');
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      renderHistory(data.items || []);
    } catch (err) {
      historicoLista.innerHTML = `<div class="ea-mini-item"><strong>Falha ao carregar historico</strong><p>${esc(err instanceof Error ? err.message : 'erro desconhecido')}</p></div>`;
    }
  }

  async function extractTextFromFile(file) {
    if (file.type === 'application/pdf') {
      if (!pdfLib?.getDocument) throw new Error('Leitor de PDF indisponivel no momento.');
      const pdf = await pdfLib.getDocument({ data: await file.arrayBuffer() }).promise;
      let fullText = '';
      const totalPages = Math.min(pdf.numPages, 30);
      for (let i = 1; i <= totalPages; i++) {
        showStatus(`Lendo PDF: pagina ${i}/${totalPages}...`);
        const page = await pdf.getPage(i);
        const textContent = await page.getTextContent();
        const pageText = textContent.items.map(item => item.str).join(' ');
        if (pageText.trim().length >= 40) {
          fullText += pageText + '\n';
          continue;
        }
        const viewport = page.getViewport({ scale: 2 });
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvasContext: context, viewport }).promise;
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.95));
        const result = await Tesseract.recognize(blob, 'por');
        fullText += (result?.data?.text || '') + '\n';
      }
      return fullText;
    }
    if (file.type.startsWith('image/')) {
      showStatus('Executando OCR da imagem...');
      const result = await Tesseract.recognize(file, 'por');
      return result?.data?.text || '';
    }
    throw new Error('Tipo de arquivo nao suportado. Envie PDF ou imagem.');
  }

  async function readCurrentFile() {
    if (!currentFile) throw new Error('Selecione um arquivo antes de usar a leitura.');
    setBusy(true);
    try {
      const extracted = (await extractTextFromFile(currentFile)).trim();
      if (!extracted) throw new Error('Nao foi possivel extrair texto do arquivo enviado.');
      fields.texto_base.value = extracted;
      showStatus('Conteudo do arquivo extraido com sucesso.');
    } finally {
      setBusy(false);
    }
  }

  async function ensureTextBase() {
    if (clean(fields.texto_base.value) || !currentFile) return;
    await readCurrentFile();
  }

  async function callAssistant(action) {
    hideMessages();
    setBusy(true);
    try {
      const response = await fetch('/api/empenho-assistente', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, payload: payloadFromForm() }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      if (data.history_id) await loadHistory();
      return data;
    } finally {
      setBusy(false);
    }
  }

  fileInput.addEventListener('change', event => {
    if (event.target.files?.[0]) setFile(event.target.files[0]);
  });
  dropzone.addEventListener('dragover', event => {
    event.preventDefault();
    dropzone.classList.add('drag-over');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
  dropzone.addEventListener('drop', event => {
    event.preventDefault();
    dropzone.classList.remove('drag-over');
    if (event.dataTransfer.files?.[0]) setFile(event.dataTransfer.files[0]);
  });

  $('btn-clear-file').addEventListener('click', () => setFile(null));
  $('btn-read-file').addEventListener('click', async () => {
    try { await readCurrentFile(); } catch (err) { showError(err instanceof Error ? err.message : 'Erro ao ler arquivo.'); }
  });
  $('btn-extract').addEventListener('click', async () => {
    try {
      await ensureTextBase();
      const data = await callAssistant('extract_fields');
      renderExtraction(data.resultado || {});
      showStatus('Campos extraidos com sucesso.');
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Erro ao extrair campos.');
    }
  });
  $('btn-checklist').addEventListener('click', async () => {
    try {
      await ensureTextBase();
      const data = await callAssistant('checklist');
      renderChecklist(data.resultado || {});
      showStatus('Checklist gerado com sucesso.');
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Erro ao gerar checklist.');
    }
  });
  $('btn-generate').addEventListener('click', async () => {
    try { await ensureTextBase(); } catch (err) { showError(err instanceof Error ? err.message : 'Erro ao ler arquivo.'); return; }
    if (!clean(fields.texto_base.value)) {
      showError('Cole um texto ou envie um arquivo antes de gerar a descricao.');
      return;
    }
    try {
      const before = clean(fields.descricao_resultado.value);
      const data = await callAssistant('generate_description');
      const result = clean(data.resultado || '');
      fields.descricao_resultado.value = result;
      renderDiff(data.diff || {}, before, result);
      showStatus('Descricao gerada com sucesso.');
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Erro ao gerar descricao.');
    }
  });
  $('btn-improve').addEventListener('click', async () => {
    if (!clean(fields.descricao_resultado.value)) {
      showError('Gere ou cole uma descricao antes de melhorar.');
      return;
    }
    try {
      const before = clean(fields.descricao_resultado.value);
      const data = await callAssistant('improve_description');
      const result = clean(data.resultado || '');
      fields.descricao_resultado.value = result;
      renderDiff(data.diff || {}, before, result);
      showStatus('Descricao revisada com sucesso.');
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Erro ao melhorar descricao.');
    }
  });
  $('btn-review').addEventListener('click', async () => {
    try {
      await ensureTextBase();
      const data = await callAssistant('review_bundle');
      const result = data.resultado || {};
      renderExtraction(result.campos || {});
      renderChecklist(result.checklist || {});
      fields.descricao_resultado.value = clean(result.descricao_melhorada || result.descricao_base || '');
      renderDiff(result.diff || {}, result.descricao_base || '', result.descricao_melhorada || result.descricao_base || '');
      showStatus('Revisao completa executada com sucesso.');
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Erro ao revisar empenho.');
    }
  });
  $('btn-clear').addEventListener('click', () => {
    Object.values(fields).forEach(el => { el.value = ''; });
    setFile(null);
    painelCampos.innerHTML = '<div class="ea-mini-item"><strong>Nenhuma extracao ainda.</strong></div>';
    painelChecklist.innerHTML = '<div class="ea-mini-item"><strong>Checklist ainda nao gerado.</strong></div>';
    painelDiff.innerHTML = '<div class="ea-mini-item"><strong>Use a revisao para gerar o diff.</strong></div>';
    hideMessages();
  });
  $('btn-copy').addEventListener('click', async () => {
    const text = clean(fields.descricao_resultado.value);
    if (!text) {
      showError('Nao ha descricao para copiar.');
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      showStatus('Descricao copiada para a area de transferencia.');
    } catch {
      showError('Nao foi possivel copiar automaticamente.');
    }
  });
  $('btn-download').addEventListener('click', () => {
    const text = clean(fields.descricao_resultado.value);
    if (!text) {
      showError('Nao ha descricao para baixar.');
      return;
    }
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'descricao_empenho_assistida.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showStatus('Arquivo .txt preparado para download.');
  });
  fields.descricao_resultado.addEventListener('input', () => {
    const pos = fields.descricao_resultado.selectionStart;
    fields.descricao_resultado.value = fields.descricao_resultado.value.toUpperCase();
    fields.descricao_resultado.setSelectionRange(pos, pos);
  });

  loadHistory();
})();
