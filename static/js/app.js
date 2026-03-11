/* ============================================================
   app.js – Controle de Empenhos Mensais (versão Flask+SQLite)
   Prefeitura Municipal de Inajá
   ============================================================ */
'use strict';

// ── Constantes ─────────────────────────────────────────────
const API = `${window.location.origin}/api`;

const MESES = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
];

// ── Estado ──────────────────────────────────────────────────
let state = {
  year: new Date().getFullYear(),
  month: new Date().getMonth(),
  searchTerm: '',
  filterDept: '',
  filterStatus: '',
  filterTipo: '',
  filterCadastro: '',
  filterVencimento: '',
  expandAll: false,
  credores: [],
  empenhados: {},
  sort: { col: 'nome', dir: 'asc' },
  totalCredores: 0,
  summary: null,
};

let _filterCacheKey = '';
let _filterCacheResult = [];
let _searchDebounceTimer = null;
let _brasaoB64Promise = null;

function invalidateFilterCache() {
  _filterCacheKey = '';
  _filterCacheResult = [];
}

function getFilterCacheKey() {
  const empenhoKeys = Object.keys(state.empenhados).sort().join(',');
  return JSON.stringify({
    year: state.year,
    month: state.month,
    search: state.searchTerm,
    dept: state.filterDept,
    status: state.filterStatus,
    tipo: state.filterTipo,
    cadastro: state.filterCadastro,
    vencimento: state.filterVencimento,
    sortCol: state.sort.col,
    sortDir: state.sort.dir,
    credoresLen: state.credores.length,
    empenhos: empenhoKeys,
  });
}

// ── API Calls ────────────────────────────────────────────────
async function apiGet(path) {
  const r = await fetch(API + path);
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || `GET ${path} → ${r.status}`);
  }
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || `POST ${path} → ${r.status}`);
  }
  return r.json();
}

async function apiPut(path, body) {
  const r = await fetch(API + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || `PUT ${path} → ${r.status}`);
  }
  return r.json();
}

async function apiDelete(path) {
  const r = await fetch(API + path, { method: 'DELETE' });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || `DELETE ${path} → ${r.status}`);
  }
  return r.json();
}

function shouldRequestSummary() {
  return !state.searchTerm
    && !state.filterDept
    && !state.filterTipo
    && !state.filterCadastro
    && !state.filterVencimento;
}

async function ensureBrasaoB64() {
  if (typeof BRASAO_B64 !== 'undefined' && BRASAO_B64) return BRASAO_B64;
  if (_brasaoB64Promise) return _brasaoB64Promise;
  _brasaoB64Promise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = '/static/js/brasao_b64.js';
    script.async = true;
    script.onload = () => resolve(typeof BRASAO_B64 !== 'undefined' ? BRASAO_B64 : '');
    script.onerror = () => reject(new Error('Falha ao carregar brasão otimizado'));
    document.head.appendChild(script);
  });
  return _brasaoB64Promise;
}

async function loadCredores() {
  const params = new URLSearchParams({
    limit: '1000',
    offset: '0',
    sort_col: state.sort.col,
    sort_dir: state.sort.dir,
  });
  if (state.searchTerm) params.set('search', state.searchTerm);
  if (state.filterDept) params.set('departamento', state.filterDept);
  if (state.filterTipo) params.set('tipo', state.filterTipo);
  if (state.filterCadastro) params.set('status_cadastro', state.filterCadastro);
  if (state.filterVencimento === 'vencidos') {
    params.set('somente_vencidos', '1');
  } else if (state.filterVencimento === '30') {
    params.set('vencendo_dias', '30');
  }
  if (shouldRequestSummary()) {
    params.set('include_summary', '1');
  }
  const res = await apiGet(`/credores?${params.toString()}`);
  const items = Array.isArray(res)
    ? res
    : (Array.isArray(res?.items) ? res.items : []);
  state.credores = items;
  state.totalCredores = Array.isArray(res) ? items.length : (Number(res?.total) || items.length);
  state.summary = Array.isArray(res) ? null : (res?.summary || null);
  invalidateFilterCache();
  return res;
}

// ── Carregar dados do mês ────────────────────────────────────
async function loadMonth() {
  const m = state.month + 1;
  state.empenhados = {};
  try {
    const [empList] = await Promise.all([
      apiGet(`/empenhos/${state.year}/${m}`),
    ]);
    empList.forEach(e => {
      state.empenhados[e.credor_id] = true;
    });
    return { ok: true };
  } catch (err) {
    console.warn(`Falha ao carregar empenhos de ${m}/${state.year}:`, err);
    return { ok: false, error: err };
  }
}

// ── Helpers de formatação ────────────────────────────────────
function formatBRL(value) {
  if (!value || value === 0) return 'A definir';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL',
  }).format(value);
}

// ── Render ───────────────────────────────────────────────────
let _renderPending = false;
function render() {
  if (_renderPending) return;
  _renderPending = true;
  requestAnimationFrame(() => {
    _renderPending = false;
    renderMonthNav();
    renderCards();
    renderStats();
  });
}

async function autosaveGeneratedText(text, options) {
  if (!window.DocumentAutosave) return;
  try {
    await window.DocumentAutosave.saveText(text, options);
  } catch (err) {
    console.warn('Falha ao salvar documento gerado automaticamente:', err);
  }
}

function downloadGeneratedBlob(blob, fileName) {
  if (window.DocumentAutosave) {
    window.DocumentAutosave.downloadBlob(blob, fileName);
    return;
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

function renderMonthNav() {
  document.getElementById('current-month-name').textContent = MESES[state.month];
  document.getElementById('current-month-year').textContent = state.year;
}

function filteredCredores() {
  const cacheKey = getFilterCacheKey();
  if (_filterCacheKey === cacheKey) return _filterCacheResult;
  const credores = Array.isArray(state.credores) ? state.credores : [];
  const list = credores.filter(c => {
    if (state.filterStatus) {
      const done = !!state.empenhados[c.id];
      if (state.filterStatus === 'empenhado' && !done) return false;
      if (state.filterStatus === 'pendente' && done) return false;
    }
    return true;
  });
  _filterCacheKey = cacheKey;
  _filterCacheResult = list;
  return list;
}

function renderCards() {
  const grid = document.getElementById('empenhos-grid');
  const empty = document.getElementById('empty-state');
  const list = filteredCredores();

  grid.innerHTML = '';

  if (list.length === 0) {
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  const fragment = document.createDocumentFragment();

  list.forEach((c, idx) => {
    const done = !!state.empenhados[c.id];
    fragment.appendChild(buildCard(c, done, idx));
  });
  grid.appendChild(fragment);
}

function buildCard(c, done, idx) {
  const div = document.createElement('div');
  div.className = `empenho-card${done ? ' done' : ''}${state.expandAll ? ' expanded' : ''}`;
  div.dataset.id = c.id;

  const dept = c.departamento || '';
  const tipo = c.tipo_valor || 'FIXO';
  const valor = c.valor || 0;
  const obs = c.obs || '';

  // Vencimento badge
  let vencimentoBadge = '';
  if (c.validade) {
    const valDate = new Date(c.validade + 'T00:00:00');
    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);
    const diffDias = Math.ceil((valDate - hoje) / (1000 * 60 * 60 * 24));
    if (diffDias < 0) {
      vencimentoBadge = `<span class="badge-vencimento vencido" title="Contrato vencido em ${valDate.toLocaleDateString('pt-BR')}">VENCIDO</span>`;
    } else if (diffDias <= 30) {
      vencimentoBadge = `<span class="badge-vencimento atencao" title="Contrato vence em ${valDate.toLocaleDateString('pt-BR')}">⚠️ ${diffDias}d</span>`;
    }
  }
  const isVariavel = tipo.toUpperCase().includes('VAR');
  const valorStr = (isVariavel && !valor) ? '— variável' : formatBRL(valor);

  const deptClass = {
    'ADMINISTRAÇÃO': 'dept-admin',
    'ASSISTÊNCIA SOCIAL': 'dept-social',
    'EDUCAÇÃO': 'dept-edu',
    'SAÚDE': 'dept-saude',
  }[dept] || 'dept-outro';

  const tipoClass = isVariavel ? 'tipo-variavel' : 'tipo-fixo';

  div.innerHTML = `
    <div class="card-row">
      <div class="col-name">
        <span class="card-name" title="Clique para copiar" style="cursor:pointer;">${c.nome || '—'}${vencimentoBadge}${obs ? `<span class="badge-obs">${obs}</span>` : ''}</span>
        <span class="card-desc">${c.descricao || '—'}</span>
      </div>
      <div class="col-dept">
        ${dept ? `<span class="badge-dept ${deptClass}">${dept}</span>` : '<span class="badge-dept dept-outro">—</span>'}
      </div>
      <div class="col-valor">${valorStr}</div>
      <div class="col-tipo">
        <span class="badge-tipo ${tipoClass}">${isVariavel ? 'Variável' : 'Fixo'}</span>
      </div>
      <div class="col-action">
        <button class="btn-expand" data-action="expand" title="Ver detalhes">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6"/></svg>
        </button>
        <button class="btn-edit" data-action="edit" title="Editar">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </button>
        <button class="btn-print" data-action="print" title="Imprimir">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
        </button>
        <button class="btn-empenhar ${done ? 'done-btn' : 'pending'}" data-action="toggle">
          ${done ? '✓ Empenhado' : '○ Empenhar'}
        </button>
      </div>
    </div>
    <div class="card-details">
      ${c.cnpj ? `<div class="detail-row"><span class="detail-label">CNPJ</span><span class="detail-value">${c.cnpj}</span></div>` : ''}
      ${c.email ? `<div class="detail-row"><span class="detail-label">E-mail</span><span class="detail-value">${c.email}</span></div>` : ''}
      ${c.solicitacao ? `<div class="detail-row"><span class="detail-label">Solicitação</span><span class="detail-value">${c.solicitacao}</span></div>` : ''}
      ${c.pagamento ? `<div class="detail-row"><span class="detail-label">Pagamento</span><span class="detail-value">${c.pagamento} dias</span></div>` : ''}
      <div class="detail-row hist-row">
        <span class="detail-label">Histórico</span>
        <div class="historico-pills" id="hist-${c.id}"><span style="font-size:11px;color:var(--text-3)">▸ expandir para carregar</span></div>
      </div>
    </div>
  `;

  return div;
}

function copyCredorName(nome, el) {
  const feedbackCopy = () => {
    const orig = el.style.color;
    el.style.color = 'var(--green-dark, #16a34a)';
    const prevTitle = el.title;
    el.title = 'Copiado!';
    setTimeout(() => { el.style.color = orig; el.title = prevTitle; }, 1200);
    showToast(`"${nome}" copiado!`, 'success');
  };
  const fallbackCopy = () => {
    const ta = document.createElement('textarea');
    ta.value = nome;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try { document.execCommand('copy'); } catch (_) {}
    document.body.removeChild(ta);
    feedbackCopy();
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(nome).then(feedbackCopy).catch(fallbackCopy);
  } else {
    fallbackCopy();
  }
}

function handleCardExpand(cardEl, credorId) {
  cardEl.classList.toggle('expanded');
  if (!cardEl.classList.contains('expanded')) return;
  const histEl = cardEl.querySelector('.historico-pills');
  if (histEl && !histEl.dataset.loaded) {
    histEl.innerHTML = '<span style="font-size:11px;color:var(--text-3)">...</span>';
    apiGet(`/credores/${credorId}/historico?meses=6`).then(hist => {
      histEl.innerHTML = hist.map(h =>
        `<span class="hist-pill ${h.empenhado ? 'hist-emp' : 'hist-pend'}" title="${h.mes_nome}/${h.ano}">${h.mes_nome}</span>`
      ).join('');
      histEl.dataset.loaded = '1';
    }).catch(() => { histEl.innerHTML = '<span style="font-size:11px;color:var(--text-3)">—</span>'; });
  }
}

// ── Stats ─────────────────────────────────────────────────────
function renderStats() {
  const credores = filteredCredores();
  let doneCt = 0, pendCt = 0, valorDone = 0, valorPend = 0;

  credores.forEach(c => {
    const done = !!state.empenhados[c.id];
    const isVar = (c.tipo_valor || '').toUpperCase().includes('VAR');
    const v = isVar ? 0 : (Number(c.valor) || 0);
    if (done) { doneCt++; valorDone += v; }
    else { pendCt++; valorPend += v; }
  });

  const total = credores.length;
  const pct = total > 0 ? Math.round((doneCt / total) * 100) : 0;

  document.getElementById('stat-total').textContent = total;
  document.getElementById('stat-done').textContent = doneCt;
  document.getElementById('stat-pending').textContent = pendCt;
  document.getElementById('stat-valor').textContent = formatBRL(valorDone);
  document.getElementById('stat-restante').textContent = formatBRL(valorPend);
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-label').textContent = `${pct}% concluído`;
  const counterEl = document.getElementById('credores-counter');
  if (counterEl) {
    const totalBase = state.summary?.total ?? state.totalCredores ?? total;
    counterEl.textContent = `${total} exibidos de ${totalBase} cadastrados`;
  }
  const summaryEl = document.getElementById('credores-summary');
  if (summaryEl && state.summary) {
    summaryEl.textContent = `Fixos: ${state.summary.fixos || 0} | Variáveis: ${state.summary.variaveis || 0} | Sem CNPJ: ${state.summary.sem_cnpj || 0} | Sem e-mail: ${state.summary.sem_email || 0} | Vencidos: ${state.summary.vencidos || 0} | Vencendo 30d: ${state.summary.vencendo_30 || 0}`;
  }

  // Dept breakdown
  const depts = {};
  credores.forEach(c => {
    const d = c.departamento || 'OUTRO';
    if (!depts[d]) depts[d] = { total: 0, done: 0, valor: 0 };
    depts[d].total++;
    if (state.empenhados[c.id]) { depts[d].done++; depts[d].valor += (Number(c.valor) || 0); }
  });
  const deptColors = { 'ADMINISTRAÇÃO': 'var(--blue)', 'ASSISTÊNCIA SOCIAL': 'var(--purple)', 'EDUCAÇÃO': 'var(--green)', 'SAÚDE': 'var(--orange)' };
  const deptEl = document.getElementById('dept-stats-row');
  if (deptEl) {
    deptEl.innerHTML = Object.entries(depts).sort((a,b) => b[1].total - a[1].total).map(([d, s]) =>
      `<button class="dept-stat-btn" data-dept="${d}" style="--dept-color:${deptColors[d]||'var(--text-3)'}">
        <span class="dept-stat-name">${d.split(' ')[0]}</span>
        <span class="dept-stat-count">${s.done}/${s.total}</span>
        <span class="dept-stat-valor">${s.valor > 0 ? formatBRL(s.valor) : '—'}</span>
      </button>`
    ).join('');
    deptEl.querySelectorAll('.dept-stat-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const d = btn.dataset.dept;
        const sel = document.getElementById('filter-dept');
        if (state.filterDept === d) { sel.value = ''; state.filterDept = ''; btn.classList.remove('active-dept'); }
        else { sel.value = d; state.filterDept = d; deptEl.querySelectorAll('.dept-stat-btn').forEach(b => b.classList.remove('active-dept')); btn.classList.add('active-dept'); }
        setLoading(true);
        try {
          await loadCredores();
          render();
        } finally {
          setLoading(false);
        }
      });
    });
    // Restore active state from current filter
    if (state.filterDept) {
      const activeBtn = deptEl.querySelector(`.dept-stat-btn[data-dept="${state.filterDept}"]`);
      if (activeBtn) activeBtn.classList.add('active-dept');
    }
  }
}

// ── Template CSS compartilhado (print) ───────────────────────
function _printCSS() {
  return `
    @page { margin: 12mm 15mm; size: A4 portrait; }
    * { margin:0; padding:0; box-sizing:border-box;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important; }
    body {
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 11pt;
      color: #000;
      background: #fff;
    }

    /* ── Faixa superior Oficial ── */
    .doc-header {
      display: flex;
      align-items: center;
      border: 2px solid #000;
      padding: 10px;
      margin-bottom: 20px;
      border-radius: 4px;
    }
    .doc-header-brasao { width: 70px; height: auto; object-fit: contain; margin-right: 15px; }
    .doc-header-text { flex: 1; text-align: center; }
    .doc-header-text h1 { font-size: 14pt; font-weight: bold; text-transform: uppercase; margin-bottom: 2px; }
    .doc-header-text h2 { font-size: 11pt; font-weight: normal; margin-bottom: 4px; }
    .doc-header-text h3 { font-size: 12pt; font-weight: bold; text-transform: uppercase; border-top: 1px solid #000; margin-top: 4px; padding-top: 4px; }
    
    .doc-header-right {
       text-align: right; 
       font-size: 9pt; 
       padding-left: 15px; 
       border-left: 1px solid #ccc;
    }
    .doc-ref { font-weight: bold; font-size: 11pt; margin-top: 4px; }

    /* ── Corpo ── */
    .doc-body { margin-bottom: 25px; position: relative; }

    /* ── Marca D'Agua ── */
    .watermark-done {
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
    }

    /* ── Tabela de Dados ── */
    table.doc-table { 
      width: 100%; 
      border-collapse: collapse; 
      margin-bottom: 15px; 
      position: relative;
      z-index: 1;
    }
    table.doc-table th, table.doc-table td { 
      border: 1px solid #000; 
      padding: 8px; 
      vertical-align: middle; 
    }
    table.doc-table th { 
      background: #f0f0f0; 
      text-transform: uppercase; 
      font-size: 9pt; 
      width: 30%; 
      text-align: left;
    }
    table.doc-table td { font-size: 10pt; font-weight: 500; }

    /* ── Caixa de valor ── */
    .valor-box {
      border: 2px solid #000;
      background: #fdfdfd;
      padding: 12px;
      text-align: center;
      margin-bottom: 30px;
      border-radius: 4px;
    }
    .vb-label { font-size: 11pt; font-weight: bold; text-transform: uppercase; margin-bottom: 5px; }
    .vb-value { font-size: 18pt; font-weight: bold; }

    /* ── Data e Assinaturas ── */
    .sign-date {
      text-align: right; margin-bottom: 40px; font-size: 11pt;
    }

    .sign-section {
      display: flex;
      justify-content: space-around;
      margin-top: 50px;
    }
    .sign-block { text-align: center; width: 40%; }
    .sign-line-top {
      border-bottom: 1px solid #000;
      margin-bottom: 8px;
      height: 40px; /* Space for signature */
    }
    .sign-label { font-size: 10pt; font-weight: bold; text-transform: uppercase; }
    .sign-sub { font-size: 9pt; margin-top: 2px; }

    /* ── Rodapé de Autenticidade ── */
    .doc-footer {
      text-align: center;
      font-size: 8pt;
      color: #555;
      margin-top: 30px;
      border-top: 1px solid #ccc;
      padding-top: 5px;
    }
  `;
}

// ── Bloco HTML de uma página de credor ───────────────────────
function _buildDocPage(c, done, mesNome, ano, isLast) {
  const isVar = (c.tipo_valor || '').toUpperCase().includes('VAR');
  const valorStr = (isVar && !c.valor) ? 'Valor variável' : formatBRL(c.valor || 0);
  const pb = isLast ? '' : 'page-break-after:always;';
  
  const watermark = done ? '<div class="watermark-done">EMPENHADO</div>' : '';

  const campos = [
    ['Departamento Solicitante', c.departamento],
    ['Credor / Fornecedor', c.nome],
    ['CNPJ / CPF', c.cnpj],
    ['Descrição do Objeto / Serviço', c.descricao],
    ['Tipo de Valor', c.tipo_valor],
    ['Observações', c.obs],
  ].filter(([, v]) => v && String(v).trim());

  const tableRows = campos.map(([l, v]) =>
    `<tr><th>${l}</th><td>${v}</td></tr>`
  ).join('');

  return `
    <div style="${pb} position: relative;">
      <div class="doc-header">
        <img class="doc-header-brasao" src="${typeof BRASAO_B64 !== 'undefined' && BRASAO_B64 ? BRASAO_B64 : '/static/img/brasao.png'}" alt="Brasão" />
        <div class="doc-header-text">
          <h1>Estado do Paraná</h1>
          <h2>Prefeitura Municipal de Inajá</h2>
          <h3>Solicitação de Empenho de Despesa Fixa / Contínua</h3>
        </div>
        <div class="doc-header-right">
          <div>Referência</div>
          <div class="doc-ref">${mesNome} / ${ano}</div>
        </div>
      </div>

      <div class="doc-body">
        ${watermark}
        <table class="doc-table">${tableRows}</table>

        <div class="valor-box">
          <div class="vb-label">Valor do Empenho</div>
          <div class="vb-value">${valorStr}</div>
        </div>

        <div class="sign-date">
          Inajá / PR, _____ de ___________________ de ${ano}.
        </div>

        <div class="sign-section">
          <div class="sign-block" style="width: 50%;">
             <div class="sign-line-top"></div>
             <div class="sign-label">Ordenador de Despesa</div>
             <div class="sign-sub">Prefeitura Municipal de Inajá</div>
          </div>
        </div>
        
        <div class="doc-footer">
           Documento gerado eletronicamente pelo módulo de Controle de Despesas Fixas.
        </div>
      </div>
    </div>`;
}

// ── Exportar CSV ───────────────────────────────────────────────
async function exportCSV() {
  const lista = filteredCredores();
  if (!lista.length) { showToast('Nenhum credor para exportar', 'error'); return; }
  const mesNome = MESES[state.month];
  const ano = state.year;
  const header = ['Nome', 'Departamento', 'Valor', 'Tipo', 'CNPJ', 'Descrição', 'Status', 'Observações'];
  const rows = lista.map(c => [
    c.nome || '',
    c.departamento || '',
    (c.valor || 0).toFixed(2).replace('.', ','),
    c.tipo_valor || 'FIXO',
    c.cnpj || '',
    c.descricao || '',
    state.empenhados[c.id] ? 'Empenhado' : 'Pendente',
    c.obs || '',
  ]);
  const csv = [header, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\r\n');
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
  const fileName = `credores_${mesNome}_${ano}.csv`;
  await autosaveGeneratedText('\ufeff' + csv, {
    nome: fileName,
    categoria: 'relatorios_csv',
    referencia: `${ano}-${String(state.month + 1).padStart(2, '0')}`,
    descricao: `Exportação CSV de credores fixos de ${mesNome}/${ano}`,
    mimeType: 'text/csv;charset=utf-8;'
  });
  downloadGeneratedBlob(blob, fileName);
  showToast(`CSV exportado: ${lista.length} credores`, 'success');
}

// ── Empenhar em Lote ───────────────────────────────────────────
async function batchEmpenhar() {
  const pending = filteredCredores().filter(c => !state.empenhados[c.id]);
  if (pending.length === 0) { showToast('Nenhum credor pendente na lista atual', 'info'); return; }
  if (!confirm(`Empenhar ${pending.length} credor(es) pendente(s) de ${MESES[state.month]}/${state.year}?`)) return;
  setLoading(true);
  try {
    const results = await apiPost('/empenhos/lote', {
      itens: pending.map(c => ({ credor_id: c.id, ano: state.year, mes: state.month + 1 }))
    });
    (results.resultados || []).forEach(res => {
      state.empenhados[res.credor_id] = !!res.empenhado;
    });
    invalidateFilterCache();
    showToast(`✓ ${pending.length} credor(es) empenhado(s)!`, 'success');
    render();
  } catch (e) {
    showToast('Erro ao empenhar em lote', 'error');
    console.error(e);
  } finally {
    setLoading(false);
  }
}

// ── Imprimir Credor (individual) ──────────────────────────────
async function printCredor(c) {
  try { await ensureBrasaoB64(); } catch (_) {}
  const done = !!state.empenhados[c.id];
  const mesNome = MESES[state.month];
  const ano = state.year;

  const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Solicita&#231;&#227;o &ndash; ${c.nome}</title>
  <style>${_printCSS()}</style>
</head>
<body>
  ${_buildDocPage(c, done, mesNome, ano, true)}
  <script>window.onload=function(){window.print();window.onafterprint=function(){window.close();};};<\/script>
</body></html>`;

  await autosaveGeneratedText(html, {
    nome: `solicitacao_${(c.nome || 'credor').replace(/[^a-z0-9]+/gi, '_')}_${ano}_${state.month + 1}.html`,
    categoria: 'relatorios_html',
    referencia: `${ano}-${String(state.month + 1).padStart(2, '0')}`,
    descricao: `Relatório individual gerado para ${c.nome || 'credor'}`,
    mimeType: 'text/html;charset=utf-8;'
  });

  const win = window.open('', '_blank', 'width=760,height=750');
  if (!win) {
    showToast('Bloqueador de popups ativado. Permita popups para imprimir.', 'error');
    return;
  }
  win.document.write(html);
  win.document.close();
}

// ── Imprimir em Lote ─────────────────────────────────────────
async function printLote() {
  const lista = filteredCredores();
  if (lista.length === 0) { showToast('Nenhum credor para imprimir', 'error'); return; }
  try { await ensureBrasaoB64(); } catch (_) {}

  const mesNome = MESES[state.month];
  const ano = state.year;

  const pages = lista.map((c, i) =>
    _buildDocPage(c, !!state.empenhados[c.id], mesNome, ano, i === lista.length - 1)
  ).join('');

  const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Lote &ndash; ${mesNome} ${ano}</title>
  <style>${_printCSS()}</style>
</head>
<body>
  ${pages}
  <script>window.onload=function(){window.print();window.onafterprint=function(){window.close();};};<\/script>
</body></html>`;

  await autosaveGeneratedText(html, {
    nome: `solicitacoes_lote_${ano}_${state.month + 1}.html`,
    categoria: 'relatorios_html',
    referencia: `${ano}-${String(state.month + 1).padStart(2, '0')}`,
    descricao: `Relatório em lote de ${lista.length} credores para ${mesNome}/${ano}`,
    mimeType: 'text/html;charset=utf-8;'
  });

  const win = window.open('', '_blank', 'width=760,height=750');
  if (!win) {
    showToast('Bloqueador de popups ativado. Permita popups para imprimir.', 'error');
    return;
  }
  win.document.write(html);
  win.document.close();
}

// ── Toggle Empenho ────────────────────────────────────────────
async function onToggle(id, nome) {
  try {
    setLoading(true);
    const res = await apiPost('/empenhos', {
      credor_id: id,
      ano: state.year,
      mes: state.month + 1,
    });
    state.empenhados[id] = res.empenhado;
    invalidateFilterCache();
    render();
    showToast(
      res.empenhado ? `✓ ${nome} empenhado!` : `↩ ${nome} desmarcado`,
      res.empenhado ? 'success' : 'info'
    );
  } catch (e) {
    showToast('Erro ao salvar empenho', 'error');
    console.error(e);
  } finally {
    setLoading(false);
  }
}

// ── Modal: Adicionar / Editar Credor ─────────────────────────
let editingId = null;

function openModal(id = null) {
  editingId = id;
  document.getElementById('credor-form').reset();
  document.getElementById('form-id').value = '';

  const modal = document.getElementById('modal-overlay');
  const delBtn = document.getElementById('btn-delete-credor');

  if (id !== null) {
    const c = state.credores.find(x => x.id === id);
    if (!c) return;
    document.getElementById('modal-title').textContent = 'Editar Credor';
    delBtn.style.display = 'flex';
    document.getElementById('form-id').value = c.id;
    document.getElementById('form-nome').value = c.nome || '';
    document.getElementById('form-dept').value = c.departamento || 'ADMINISTRAÇÃO';
    document.getElementById('form-valor').value = c.valor || '';
    document.getElementById('form-tipo').value = c.tipo_valor || 'FIXO';
    document.getElementById('form-descricao').value = c.descricao || '';
    document.getElementById('form-cnpj').value = c.cnpj || '';
    document.getElementById('form-email').value = c.email || '';
    document.getElementById('form-pagamento').value = c.pagamento || '';
    document.getElementById('form-validade').value = c.validade || '';
    document.getElementById('form-obs').value = c.obs || '';
  } else {
    document.getElementById('modal-title').textContent = 'Novo Credor';
    delBtn.style.display = 'none';
  }

  modal.style.display = '';
  modal.classList.add('open');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  editingId = null;
}

async function onFormSubmit(e) {
  e.preventDefault();
  const nome = document.getElementById('form-nome').value.trim();
  if (!nome) { showToast('Informe o nome do credor', 'error'); return; }
  const email = document.getElementById('form-email').value.trim();
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showToast('E-mail inválido', 'error'); return;
  }
  const valorRaw = document.getElementById('form-valor').value;
  if (valorRaw && isNaN(parseFloat(valorRaw))) {
    showToast('Valor deve ser numérico', 'error'); return;
  }

  const payload = {
    nome,
    departamento: document.getElementById('form-dept').value,
    valor: parseFloat(document.getElementById('form-valor').value) || 0,
    tipo_valor: document.getElementById('form-tipo').value,
    descricao: document.getElementById('form-descricao').value.trim(),
    cnpj: document.getElementById('form-cnpj').value.trim(),
    email: document.getElementById('form-email').value.trim(),
    pagamento: document.getElementById('form-pagamento').value.trim(),
    validade: document.getElementById('form-validade').value,
    obs: document.getElementById('form-obs').value.trim(),
  };

  try {
    setLoading(true);
    const idVal = parseInt(document.getElementById('form-id').value);
    if (!isNaN(idVal) && idVal > 0) {
      await apiPut(`/credores/${idVal}`, payload);
      showToast('Credor atualizado!', 'success');
    } else {
      await apiPost('/credores', payload);
      showToast('Credor adicionado!', 'success');
    }
    await loadCredores();
    closeModal();
    render();
  } catch (err) {
    showToast(err.message || 'Erro ao salvar credor', 'error');
    console.error(err);
  } finally {
    setLoading(false);
  }
}

async function onDeleteCredor() {
  const idVal = parseInt(document.getElementById('form-id').value);
  if (!idVal) return;
  try {
    setLoading(true);
    await apiDelete(`/credores/${idVal}`);
    await loadCredores();
    delete state.empenhados[idVal];
    invalidateFilterCache();
    closeModal();
    render();
    showToast('Credor removido', 'info');
  } catch (err) {
    showToast(err.message || 'Erro ao remover', 'error');
  } finally {
    setLoading(false);
  }
}

// ── Loading Overlay ───────────────────────────────────────────
function setLoading(on) {
  document.getElementById('loading-overlay').style.display = on ? 'flex' : 'none';
}

// ── Toast ─────────────────────────────────────────────────────
let toastTimer = null;
function showToast(msg, type = 'info') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2800);
}

// ── Eventos ───────────────────────────────────────────────────
function attachEvents() {
  const grid = document.getElementById('empenhos-grid');
  grid.addEventListener('click', e => {
    const cardEl = e.target.closest('.empenho-card');
    if (!cardEl) return;
    const credorId = Number(cardEl.dataset.id);
    const credor = state.credores.find(x => x.id === credorId);
    if (!credor) return;

    const nameEl = e.target.closest('.card-name');
    if (nameEl) {
      e.stopPropagation();
      copyCredorName(credor.nome || '', nameEl);
      return;
    }

    const actionBtn = e.target.closest('[data-action]');
    if (!actionBtn) return;
    e.stopPropagation();
    const action = actionBtn.dataset.action;
    if (action === 'toggle') onToggle(credor.id, credor.nome);
    else if (action === 'expand') handleCardExpand(cardEl, credor.id);
    else if (action === 'edit') openModal(credor.id);
    else if (action === 'print') printCredor(credor);
  });

  document.getElementById('btn-prev-month').addEventListener('click', async () => {
    if (state.month === 0) { state.month = 11; state.year--; }
    else state.month--;
    setLoading(true);
    await loadMonth();
    invalidateFilterCache();
    setLoading(false);
    render();
  });

  document.getElementById('btn-next-month').addEventListener('click', async () => {
    if (state.month === 11) { state.month = 0; state.year++; }
    else state.month++;
    setLoading(true);
    await loadMonth();
    invalidateFilterCache();
    setLoading(false);
    render();
  });

  document.getElementById('search-input').addEventListener('input', e => {
    const nextValue = e.target.value;
    clearTimeout(_searchDebounceTimer);
    _searchDebounceTimer = setTimeout(async () => {
      state.searchTerm = nextValue;
      setLoading(true);
      try {
        await loadCredores();
        render();
      } finally {
        setLoading(false);
      }
    }, 120);
  });

  document.getElementById('filter-dept').addEventListener('change', async e => {
    state.filterDept = e.target.value;
    document.querySelectorAll('.dept-stat-btn').forEach(b => b.classList.remove('active-dept'));
    if (state.filterDept) {
      const btn = document.querySelector(`.dept-stat-btn[data-dept="${state.filterDept}"]`);
      if (btn) btn.classList.add('active-dept');
    }
    setLoading(true);
    try {
      await loadCredores();
      render();
    } finally {
      setLoading(false);
    }
  });

  document.getElementById('filter-status').addEventListener('change', e => {
    state.filterStatus = e.target.value;
    invalidateFilterCache();
    render();
  });

  document.getElementById('filter-tipo').addEventListener('change', async e => {
    state.filterTipo = e.target.value;
    setLoading(true);
    try {
      await loadCredores();
      render();
    } finally {
      setLoading(false);
    }
  });

  document.getElementById('filter-cadastro').addEventListener('change', async e => {
    state.filterCadastro = e.target.value;
    setLoading(true);
    try {
      await loadCredores();
      render();
    } finally {
      setLoading(false);
    }
  });

  document.getElementById('filter-vencimento').addEventListener('change', async e => {
    state.filterVencimento = e.target.value;
    setLoading(true);
    try {
      await loadCredores();
      render();
    } finally {
      setLoading(false);
    }
  });

  document.getElementById('btn-expand-all').addEventListener('click', () => {
    state.expandAll = !state.expandAll;
    document.querySelectorAll('.empenho-card').forEach(c => c.classList.toggle('expanded', state.expandAll));
    const btn = document.getElementById('btn-expand-all');
    const svgExpand = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>`;
    btn.innerHTML = state.expandAll
      ? `${svgExpand} Recolher`
      : `${svgExpand} Expandir`;
  });

  document.getElementById('btn-print-lote').addEventListener('click', printLote);

  document.getElementById('btn-add-credor').addEventListener('click', () => openModal(null));

  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('btn-modal-cancel').addEventListener('click', closeModal);
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('modal-overlay')) closeModal();
  });

  document.getElementById('credor-form').addEventListener('submit', onFormSubmit);

  document.getElementById('btn-delete-credor').addEventListener('click', () => {
    if (confirm('Tem certeza que deseja remover este credor?')) {
      const password = prompt('Digite a senha de administrador para confirmar a exclusão:');
      if (password === '1999') {
        onDeleteCredor();
      } else if (password !== null) {
        showToast('Senha incorreta', 'error');
      }
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });

  // Logs modal
  (function() {
    const PAGE_SIZE = 30;
    let currentAcao = '';
    let currentOffset = 0;
    let currentTotal = 0;

    const iconMap = {
      'CRIAR':      { icon: '＋', cls: 'criar' },
      'EDITAR':     { icon: '✎',  cls: 'editar' },
      'EXCLUIR':    { icon: '✕',  cls: 'excluir' },
      'EMPENHAR':   { icon: '✓',  cls: 'empenhar' },
      'DESEMPENHAR':{ icon: '↩',  cls: 'desempenhar' },
    };

    function renderLogItem(log) {
      const info = iconMap[log.acao] || { icon: '•', cls: 'outro' };
      const data = log.data ? new Date(log.data).toLocaleString('pt-BR') : '-';

      // Para EDITAR, renderiza o diff em chips
      let detalhesHtml = '';
      if (log.detalhes && log.acao === 'EDITAR' && log.detalhes.includes(' → ')) {
        const parts = log.detalhes.split(' | ');
        detalhesHtml = `<div class="log-diff">${parts.map(p => {
          const [label, change] = p.split(': ');
          return `<span class="log-diff-chip"><span class="log-diff-label">${label}</span><span class="log-diff-change">${change}</span></span>`;
        }).join('')}</div>`;
      } else if (log.detalhes) {
        detalhesHtml = `<div class="log-detalhes">${log.detalhes}</div>`;
      }

      return `
        <div class="log-item">
          <div class="log-icon ${info.cls}">${info.icon}</div>
          <div class="log-content">
            <div class="log-header-row">
              <span class="log-acao ${info.cls}">${log.acao}</span>
              <span class="log-nome">${log.credor_nome || '-'}</span>
            </div>
            ${detalhesHtml}
          </div>
          <div class="log-data">${data}</div>
        </div>
      `;
    }

    async function loadLogs(reset = true) {
      const list = document.getElementById('logs-list');
      const countEl = document.getElementById('logs-count');
      const pagination = document.getElementById('logs-pagination');

      if (reset) {
        currentOffset = 0;
        list.innerHTML = '<div class="spinner" style="margin: 20px auto;"></div>';
      }

      try {
        const params = new URLSearchParams({ limit: PAGE_SIZE, offset: currentOffset });
        if (currentAcao) params.set('acao', currentAcao);
        const res = await apiGet('/logs?' + params.toString());

        // Suporte ao novo formato {logs, total} e ao antigo array
        const logs = Array.isArray(res) ? res : res.logs;
        currentTotal = Array.isArray(res) ? logs.length : res.total;

        countEl.textContent = currentTotal > 0 ? `${currentTotal}` : '';

        if (reset) {
          if (logs.length === 0) {
            list.innerHTML = '<p style="text-align:center;color:var(--text-3);padding:20px;">Nenhum registro encontrado.</p>';
          } else {
            list.innerHTML = logs.map(renderLogItem).join('');
          }
        } else {
          list.innerHTML += logs.map(renderLogItem).join('');
        }

        currentOffset += logs.length;
        const hasMore = currentOffset < currentTotal;
        pagination.style.display = hasMore ? 'flex' : 'none';

      } catch (e) {
        list.innerHTML = '<p style="text-align:center;color:var(--red);padding:20px;">Erro ao carregar logs.</p>';
      }
    }

    document.getElementById('btn-logs').addEventListener('click', () => {
      const overlay = document.getElementById('logs-overlay');
      overlay.style.display = 'flex';
      overlay.classList.add('open');
      loadLogs(true);
    });

    // Filtros
    document.querySelectorAll('.log-filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.log-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentAcao = btn.dataset.acao;
        loadLogs(true);
      });
    });

    // Carregar mais
    document.getElementById('logs-load-more').addEventListener('click', () => loadLogs(false));

    document.getElementById('logs-close').addEventListener('click', () => {
      const ov = document.getElementById('logs-overlay');
      ov.classList.remove('open');
      ov.style.display = 'none';
    });
    document.getElementById('logs-overlay').addEventListener('click', e => {
      if (e.target === document.getElementById('logs-overlay')) {
        const ov = document.getElementById('logs-overlay');
        ov.classList.remove('open');
        ov.style.display = 'none';
      }
    });
  })(); // fim do módulo logs

  // Sort columns
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const col = btn.dataset.col;
      if (state.sort.col === col) {
        state.sort.dir = state.sort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sort.col = col;
        state.sort.dir = 'asc';
      }
      invalidateFilterCache();
      document.querySelectorAll('.sort-btn').forEach(b => {
        b.classList.remove('active');
        b.querySelector('.sort-arrow').textContent = '';
      });
      btn.classList.add('active');
      btn.querySelector('.sort-arrow').textContent = state.sort.dir === 'asc' ? '↑' : '↓';
      setLoading(true);
      try {
        await loadCredores();
        render();
      } finally {
        setLoading(false);
      }
    });
  });

  document.getElementById('btn-export-csv').addEventListener('click', exportCSV);
  document.getElementById('btn-empenhar-todos').addEventListener('click', batchEmpenhar);

} // fim de attachEvents

// ── Init ──────────────────────────────────────────────────────
async function init() {
  setLoading(true);
  try {
    attachEvents();
    const [credoresResult, monthResult] = await Promise.all([
      loadCredores(),
      loadMonth(),
    ]);
    if (credoresResult && credoresResult.summary) {
      state.summary = credoresResult.summary;
    }
    render();
    if (monthResult && monthResult.ok === false) {
      showToast(`Aviso: não foi possível carregar os empenhos de ${MESES[state.month]}/${state.year}.`, 'error');
    }
  } catch (err) {
    console.error('Falha ao conectar com o servidor:', err);
    document.getElementById('empenhos-grid').innerHTML = `
          <div style="grid-column:1/-1; text-align:center; padding:60px 20px; color:#f87171;">
            <p style="font-size:18px; font-weight:700; margin-bottom:10px;">⚠️ Servidor não encontrado</p>
            <p style="color:#94a3b8;">Inicie o servidor clicando duas vezes em <strong>iniciar.bat</strong></p>
          </div>`;
    document.getElementById('empty-state').style.display = 'none';
  } finally {
    setLoading(false);
  }
}

// ── Theme Toggle ───────────────────────────────────────────────
function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else if (saved === 'vintage') {
    document.documentElement.setAttribute('data-theme', 'vintage');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
}

function syncThemeLabel() {
  const label = document.querySelector('.theme-label');
  if (!label) return;
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  if (current === 'light') label.textContent = 'Tema Escuro';
  else if (current === 'dark') label.textContent = 'Tema Vintage';
  else label.textContent = 'Tema Claro';
}

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme') || 'light';
  if (current === 'light') {
    html.setAttribute('data-theme', 'dark');
    localStorage.setItem('theme', 'dark');
  } else if (current === 'dark') {
    html.setAttribute('data-theme', 'vintage');
    localStorage.setItem('theme', 'vintage');
  } else {
    html.removeAttribute('data-theme');
    localStorage.setItem('theme', 'light');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  syncThemeLabel();
  const syncExtraThemeLabels = () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    let text = 'Tema Escuro';
    if (current === 'dark') text = 'Tema Vintage';
    if (current === 'vintage') text = 'Tema Claro';
    
    const sidebarLabel = document.querySelector('.theme-label-sidebar');
    if (sidebarLabel) sidebarLabel.textContent = text;
    const mobileLabel = document.querySelector('.theme-label-mobile');
    if (mobileLabel) mobileLabel.textContent = text;
  };
  syncExtraThemeLabels();
  
  // Hamburger menu
  const hamburger = document.getElementById('hamburger');
  const bnavMenu = document.getElementById('bnav-menu');
  const mobileNav = document.getElementById('mobile-nav');
  const mobileOverlay = document.getElementById('mobile-nav-overlay');
  const mobileNavClose = document.getElementById('mobile-nav-close');
  
  function openMobileNav() {
    hamburger?.classList.add('active');
    bnavMenu?.classList.add('active');
    mobileNav?.classList.add('open');
    mobileOverlay?.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  
  function closeMobileNav() {
    hamburger?.classList.remove('active');
    bnavMenu?.classList.remove('active');
    mobileNav?.classList.remove('open');
    mobileOverlay?.classList.remove('open');
    document.body.style.overflow = '';
  }
  
  hamburger?.addEventListener('click', () => {
    if (window.innerWidth > 860) {
      document.body.classList.toggle('sidebar-collapsed');
      const isCollapsed = document.body.classList.contains('sidebar-collapsed');
      localStorage.setItem('sidebarCollapsed', isCollapsed ? 'true' : 'false');
      return;
    }
    if (!mobileNav) return;
    if (mobileNav.classList.contains('open')) closeMobileNav();
    else openMobileNav();
  });
  
  // Load sidebar state on init
  if (localStorage.getItem('sidebarCollapsed') === 'true' && window.innerWidth > 860) {
    document.body.classList.add('sidebar-collapsed');
  }
  
  bnavMenu?.addEventListener('click', () => {
    if (!mobileNav) return;
    if (mobileNav.classList.contains('open')) closeMobileNav();
    else openMobileNav();
  });
  
  mobileOverlay?.addEventListener('click', closeMobileNav);
  mobileNavClose?.addEventListener('click', closeMobileNav);
  
  // Mobile logs button
  document.getElementById('mobile-logs')?.addEventListener('click', () => {
    closeMobileNav();
    document.getElementById('btn-logs')?.click();
  });
  document.getElementById('sidebar-logs')?.addEventListener('click', () => {
    document.getElementById('btn-logs')?.click();
  });

  // Mobile theme toggle
  const mobileThemeToggle = document.getElementById('mobile-theme-toggle');
  if (mobileThemeToggle) {
    mobileThemeToggle.addEventListener('click', () => {
      toggleTheme();
      syncThemeLabel();
      syncExtraThemeLabels();
    });
  }
  document.getElementById('sidebar-theme-toggle')?.addEventListener('click', () => {
    toggleTheme();
    syncThemeLabel();
    syncExtraThemeLabels();
  });
  
  // Dropdown menu
  const dropdownToggle = document.getElementById('dropdown-toggle');
  const dropdown = dropdownToggle?.parentElement;
  dropdownToggle?.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown?.classList.toggle('open');
  });
  document.addEventListener('click', () => dropdown?.classList.remove('open'));

  // Botão "Expandir tudo / Recolher tudo" da sidebar
  function syncSidebarExpandBtn() {
    const btn = document.getElementById('btn-sidebar-expand-all');
    const label = document.getElementById('sidebar-expand-label');
    if (!btn || !label) return;
    const sidebarGroups = document.querySelectorAll('.nav-group-sidebar');
    const allOpen = [...sidebarGroups].every(g => g.classList.contains('open'));
    if (allOpen) {
      label.textContent = 'Recolher tudo';
      btn.classList.add('expanded');
    } else {
      label.textContent = 'Expandir tudo';
      btn.classList.remove('expanded');
    }
  }

  // Sincroniza o estado inicial do botão
  syncSidebarExpandBtn();

  const btnSidebarExpandAll = document.getElementById('btn-sidebar-expand-all');
  if (btnSidebarExpandAll) {
    btnSidebarExpandAll.addEventListener('click', () => {
      const sidebarGroups = document.querySelectorAll('.nav-group-sidebar');
      const allOpen = [...sidebarGroups].every(g => g.classList.contains('open'));
      if (allOpen) {
        sidebarGroups.forEach(g => g.classList.remove('open'));
      } else {
        sidebarGroups.forEach(g => g.classList.add('open'));
      }
      syncSidebarExpandBtn();
    });
  }

  // Nav group dropdowns (Documentos / Financeiro / Ferramentas)
  document.querySelectorAll('.nav-group-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const group = btn.closest('.nav-group');
      const isSidebar = group.classList.contains('nav-group-sidebar');

      if (isSidebar) {
        // Na sidebar: toggle independente (não fecha os outros)
        group.classList.toggle('open');
        // Sincroniza o botão expandir tudo
        syncSidebarExpandBtn();
      } else {
        // No header: accordion (fecha os outros)
        const isOpen = group.classList.contains('open');
        document.querySelectorAll('.nav-group:not(.nav-group-sidebar)').forEach(g => g.classList.remove('open'));
        if (!isOpen) group.classList.add('open');
      }
    });
  });
  
  // Prevent closing when clicking inside menu (but not on links)
  document.querySelectorAll('.nav-group-menu').forEach(menu => {
    menu.addEventListener('click', e => {
      if (e.target.tagName !== 'A' && !e.target.closest('a')) {
        e.stopPropagation();
      }
    });
  });
  
  // Close dropdowns when clicking outside (somente os do header, não os da sidebar)
  document.addEventListener('click', () =>
    document.querySelectorAll('.nav-group:not(.nav-group-sidebar)').forEach(g => g.classList.remove('open'))
  );
  
  // Theme toggle in dropdown
  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    dropdown?.classList.remove('open');
    toggleTheme();
    syncThemeLabel();
    syncExtraThemeLabels();
  });
  
  // ADM Authentication — resets on every page load (never persisted)
  let isAdmAuthenticated = false;
  
  function showPasswordModal() {
    document.getElementById('password-overlay').style.display = 'flex';
    document.getElementById('password-input').value = '';
    document.getElementById('password-error').style.display = 'none';
    document.getElementById('password-input').focus();
  }
  
  function hidePasswordModal() {
    document.getElementById('password-overlay').style.display = 'none';
  }
  
  async function checkPassword() {
    const password = document.getElementById('password-input').value;
    const submitBtn = document.getElementById('password-submit');
    const errorEl  = document.getElementById('password-error');

    submitBtn.disabled = true;
    submitBtn.textContent = '…';
    errorEl.style.display = 'none';

    try {
      const resp = await fetch('/api/auth/adm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ senha: password })
      });
      const data = await resp.json();

      if (data.ok) {
        isAdmAuthenticated = true;
        hidePasswordModal();
        showAdmPanel();
        showToast('Bem-vindo à área administrativa!', 'success');
      } else {
        errorEl.style.display = 'block';
      }
    } catch (e) {
      errorEl.textContent = 'Erro de conexão. Tente novamente.';
      errorEl.style.display = 'block';
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Entrar';
    }
  }
  
  function showAdmPanel() {
    document.getElementById('adm-panel').style.display = 'block';
    document.querySelector('.stats-bar').style.display = 'none';
    document.querySelector('.progress-section').style.display = 'none';
    document.querySelector('.toolbar').style.display = 'none';
    document.querySelector('.main-content').style.display = 'none';
  }
  
  function hideAdmPanel() {
    document.getElementById('adm-panel').style.display = 'none';
    document.querySelector('.stats-bar').style.display = '';
    document.querySelector('.progress-section').style.display = '';
    document.querySelector('.toolbar').style.display = '';
    document.querySelector('.main-content').style.display = '';
  }
  
  // Handle tab clicks with auth requirement
  function setActiveTab(tabName) {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.mobile-nav-item[data-tab]').forEach(m => m.classList.remove('active'));
    document.querySelectorAll('.bottom-nav-item[data-tab]').forEach(b => b.classList.remove('active'));
    document.querySelector(`.nav-tab[data-tab="${tabName}"]`)?.classList.add('active');
    document.querySelector(`.mobile-nav-item[data-tab="${tabName}"]`)?.classList.add('active');
    document.querySelector(`.bottom-nav-item[data-tab="${tabName}"]`)?.classList.add('active');
  }

  function handleTabClick(tabName, requiresAuth) {
    if (requiresAuth && !isAdmAuthenticated) {
      showPasswordModal();
      return;
    }
    setActiveTab(tabName);
    if (tabName === 'adm') {
      showAdmPanel();
    } else {
      hideAdmPanel();
    }
  }
  
  // Desktop nav tabs
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const tabName = tab.dataset.tab;
      if (!tabName) return;
      const requiresAuth = tab.dataset.requiresAuth === 'true';
      handleTabClick(tabName, requiresAuth);
    });
  });
  
  // Mobile nav items
  document.querySelectorAll('.mobile-nav-item[data-tab]').forEach(item => {
    item.addEventListener('click', () => {
      const tabName = item.dataset.tab;
      const requiresAuth = item.dataset.requiresAuth === 'true';
      handleTabClick(tabName, requiresAuth);
      closeMobileNav();
    });
  });
  
  // Password modal events
  document.getElementById('password-close')?.addEventListener('click', hidePasswordModal);
  document.getElementById('password-submit')?.addEventListener('click', checkPassword);
  document.getElementById('password-input')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') checkPassword();
  });
  
  // ADM logout
  document.getElementById('adm-logout')?.addEventListener('click', () => {
    isAdmAuthenticated = false;
    hideAdmPanel();
    document.querySelector('.nav-tab[data-tab="credores-fixos"]')?.click();
    showToast('Saiu da área administrativa', 'info');
  });
  
  init().then(() => {
    // Auto-open ADM tab when navigated via /#adm
    if (window.location.hash === '#adm') {
      window.location.hash = '';
      document.querySelector('.nav-tab[data-tab="adm"]')?.click();
    }
  });
});
