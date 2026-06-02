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
const CREDORES_PAGE_SIZE = 50;
let state = {
  year: new Date().getFullYear(),
  month: new Date().getMonth(),
  page: 1,
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
  totalPages: 1,
  summary: null,
};

let _filterCacheKey = '';
let _filterCacheResult = [];
let _searchDebounceTimer = null;
let _filterDebounceTimer = null;
let _brasaoB64Promise = null;
let _mainAppLoaded = false;
let _mainAppLoadingPromise = null;

function invalidateFilterCache() {
  _filterCacheKey = '';
  _filterCacheResult = [];
}

function getFilterCacheKey() {
  return JSON.stringify({
    year: state.year,
    month: state.month,
    sortCol: state.sort.col,
    sortDir: state.sort.dir,
    page: state.page,
    pageSize: CREDORES_PAGE_SIZE,
    credoresLen: state.credores.length,
  });
}

// ── API Calls ────────────────────────────────────────────────
const _apiCache = new Map();
const _API_CACHE_TTL = 30_000; // 30s para GET requests (invalidado em mutações)

async function apiGet(path, { cache = false } = {}) {
  if (cache) {
    const cached = _apiCache.get(path);
    if (cached && Date.now() - cached.ts < _API_CACHE_TTL) return cached.data;
  }
  const r = await fetch(API + path);
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || `GET ${path} → ${r.status}`);
  }
  const data = await r.json();
  if (cache) _apiCache.set(path, { data, ts: Date.now() });
  return data;
}

function apiCacheInvalidate(prefix) {
  for (const key of _apiCache.keys()) {
    if (key.startsWith(prefix)) _apiCache.delete(key);
  }
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
  // Se ja tem o valor em cache (sessao), retorna direto
  if (typeof BRASAO_B64 !== 'undefined' && BRASAO_B64) return BRASAO_B64;
  if (window._brasaoB64Cache) return window._brasaoB64Cache;
  if (_brasaoB64Promise) return _brasaoB64Promise;

  // Carrega a imagem via fetch e converte para base64 (substitui o arquivo brasao_b64.js de 436KB)
  _brasaoB64Promise = fetch('/static/img/brasao.png')
    .then(r => {
      if (!r.ok) throw new Error('Falha ao carregar brasão');
      return r.blob();
    })
    .then(blob => new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        window._brasaoB64Cache = reader.result;
        resolve(reader.result);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    }))
    .catch(() => '/static/img/brasao.png'); // fallback: URL direta

  return _brasaoB64Promise;
}

function buildCredoresQueryParams({ page = state.page, limit = CREDORES_PAGE_SIZE, includeSummary = false } = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(Math.max(0, (page - 1) * limit)),
    sort_col: state.sort.col,
    sort_dir: state.sort.dir,
    ano: String(state.year),
    mes: String(state.month + 1),
  });
  if (state.searchTerm) params.set('search', state.searchTerm);
  if (state.filterDept) params.set('departamento', state.filterDept);
  if (state.filterStatus) params.set('status', state.filterStatus);
  if (state.filterTipo) params.set('tipo', state.filterTipo);
  if (state.filterCadastro) params.set('status_cadastro', state.filterCadastro);
  if (state.filterVencimento === 'vencidos') {
    params.set('somente_vencidos', '1');
  } else if (state.filterVencimento === '30') {
    params.set('vencendo_dias', '30');
  }
  if (includeSummary) params.set('include_summary', '1');
  return params;
}

async function loadCredores() {
  const params = buildCredoresQueryParams({
    page: state.page,
    limit: CREDORES_PAGE_SIZE,
    includeSummary: shouldRequestSummary(),
  });
  const res = await apiGet(`/credores?${params.toString()}`);
  const items = Array.isArray(res)
    ? res
    : (Array.isArray(res?.items) ? res.items : []);
  state.credores = items;
  state.totalCredores = Array.isArray(res) ? items.length : (Number(res?.total) || items.length);
  state.totalPages = Math.max(1, Math.ceil(state.totalCredores / CREDORES_PAGE_SIZE));
  if (state.totalCredores === 0 && state.page !== 1) {
    state.page = 1;
  }
  if (state.page > state.totalPages && state.totalCredores > 0) {
    state.page = state.totalPages;
    return loadCredores();
  }
  state.summary = Array.isArray(res) ? null : (res?.summary || null);
  invalidateFilterCache();
  return res;
}

async function loadAllCredoresForCurrentFilters() {
  const all = [];
  let page = 1;
  let total = 0;

  while (true) {
    const params = buildCredoresQueryParams({ page, limit: CREDORES_PAGE_SIZE, includeSummary: false });
    const res = await apiGet(`/credores?${params.toString()}`);
    const items = Array.isArray(res)
      ? res
      : (Array.isArray(res?.items) ? res.items : []);
    if (page === 1) {
      total = Array.isArray(res) ? items.length : (Number(res?.total) || items.length);
    }
    all.push(...items);
    if (!items.length || all.length >= total) break;
    page += 1;
  }

  return all;
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
    renderPagination();
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

async function ensureMainAppLoaded() {
  if (_mainAppLoaded) return;
  if (_mainAppLoadingPromise) return _mainAppLoadingPromise;
  _mainAppLoadingPromise = (async () => {
    setLoading(true);
    try {
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
      _mainAppLoaded = true;
    } finally {
      setLoading(false);
      _mainAppLoadingPromise = null;
    }
  })();
  return _mainAppLoadingPromise;
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
  return Array.isArray(state.credores) ? state.credores : [];
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
        <button class="btn-duplicate" data-action="duplicate" title="Duplicar credor">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
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
    apiGet(`/credores/${credorId}/historico?meses=6`, { cache: true }).then(hist => {
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

  function _setStat(id, value, isCurrency) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = isCurrency ? formatBRL(value) : value;
    if (typeof animateCounter === 'function' && value > 0) animateCounter(el, value, 600);
  }
  _setStat('stat-total', total, false);
  _setStat('stat-done', doneCt, false);
  _setStat('stat-pending', pendCt, false);
  _setStat('stat-valor', valorDone, true);
  _setStat('stat-restante', valorPend, true);
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

function renderPagination() {
  const bar = document.getElementById('credores-pagination');
  const info = document.getElementById('credores-page-info');
  const prev = document.getElementById('btn-page-prev');
  const next = document.getElementById('btn-page-next');
  if (!bar || !info || !prev || !next) return;

  const totalPages = Math.max(1, state.totalPages || 1);
  const currentPage = Math.min(Math.max(1, state.page || 1), totalPages);
  const total = state.totalCredores || 0;

  bar.style.display = totalPages > 1 ? 'flex' : 'none';
  info.textContent = `Página ${currentPage} de ${totalPages} · ${total} credores`;
  prev.disabled = currentPage <= 1;
  next.disabled = currentPage >= totalPages;
}

// ── Template CSS compartilhado (print) ───────────────────────
function _printCSS() {
  return `
    @page { margin: 12mm 15mm; size: A4 portrait; }
    @media print {
      * { margin:0 !important; padding:0 !important; box-sizing:border-box !important;
          -webkit-print-color-adjust: exact !important;
          print-color-adjust: exact !important;
          color: #000 !important;
          background-color: transparent !important;
          visibility: visible !important;
          opacity: 1 !important; }
      body { background: #fff !important; color: #000 !important; }
      table.doc-table th { background: #f0f0f0 !important; }
      .valor-box { background: #fdfdfd !important; }
    }
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
          <h3>Solicitação de Empenho</h3>
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
        
      </div>
    </div>`;
}

// ── Exportar CSV ───────────────────────────────────────────────
async function exportCSV() {
  const lista = await loadAllCredoresForCurrentFilters();
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
  const pending = (await loadAllCredoresForCurrentFilters()).filter(c => !state.empenhados[c.id]);
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

  const css = _printCSS();
  const body = _buildDocPage(c, done, mesNome, ano, true);

  const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Solicita&#231;&#227;o &ndash; ${c.nome}</title>
  <style>${css}</style>
</head>
<body>${body}
<script>
(function(){
  var t=600;
  var check=function(){if(document.readyState==='complete'){setTimeout(function(){window.print();},t);}else{setTimeout(check,50);}};
  check();
})();
<\/script>
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
  win.document.open();
  win.document.write(html);
  win.document.close();
}

// ── Imprimir em Lote ─────────────────────────────────────────
async function printLote() {
  const lista = await loadAllCredoresForCurrentFilters();
  if (lista.length === 0) { showToast('Nenhum credor para imprimir', 'error'); return; }
  try { await ensureBrasaoB64(); } catch (_) {}

  const mesNome = MESES[state.month];
  const ano = state.year;

  const pages = lista.map((c, i) =>
    _buildDocPage(c, !!state.empenhados[c.id], mesNome, ano, i === lista.length - 1)
  ).join('');

  const css = _printCSS();

  const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Lote &ndash; ${mesNome} ${ano}</title>
  <style>${css}</style>
</head>
<body>${pages}
<script>
(function(){
  var t=800;
  var check=function(){if(document.readyState==='complete'){setTimeout(function(){window.print();},t);}else{setTimeout(check,50);}};
  check();
})();
<\/script>
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
  win.document.open();
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
let pendingDeleteCredorId = null;

function getCurrentCredorName() {
  const inputName = document.getElementById('form-nome').value.trim();
  if (inputName) return inputName;
  if (editingId !== null) {
    const credor = state.credores.find(x => x.id === editingId);
    if (credor && credor.nome) return credor.nome;
  }
  if (pendingDeleteCredorId !== null) {
    const credor = state.credores.find(x => x.id === pendingDeleteCredorId);
    if (credor && credor.nome) return credor.nome;
  }
  return 'este credor';
}

function openDeleteConfirmModal(credorId = null) {
  const idVal = credorId !== null ? credorId : parseInt(document.getElementById('form-id').value, 10);
  if (!idVal) return;

  const credor = state.credores.find(x => x.id === idVal);
  const nome = credor?.nome || getCurrentCredorName();

  pendingDeleteCredorId = idVal;
  document.getElementById('delete-confirm-message').textContent = `Confirmar exclusão de ${nome}?`;

  const modal = document.getElementById('delete-confirm-overlay');
  modal.style.display = '';
  modal.classList.add('open');
}

function closeDeleteConfirmModal() {
  document.getElementById('delete-confirm-overlay').classList.remove('open');
  pendingDeleteCredorId = null;
}

function openModal(id = null) {
  editingId = id;
  closeDeleteConfirmModal();
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
    document.getElementById('form-solicitacao').value = c.solicitacao || '';
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
  closeDeleteConfirmModal();
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
  const cnpjRaw = document.getElementById('form-cnpj').value.trim();
  const cnpjDigits = cnpjRaw.replace(/\D+/g, '');
  if (cnpjDigits) {
    if (cnpjDigits.length !== 14) {
      showToast('CNPJ deve ter 14 dígitos', 'error');
      return;
    }
    if (!isValidCnpj(cnpjDigits)) {
      showToast('CNPJ inválido', 'error');
      return;
    }
  }

  const payload = {
    nome,
    departamento: document.getElementById('form-dept').value,
    valor: parseFloat(document.getElementById('form-valor').value) || 0,
    tipo_valor: document.getElementById('form-tipo').value,
    descricao: document.getElementById('form-descricao').value.trim(),
    cnpj: cnpjDigits,
    email: document.getElementById('form-email').value.trim(),
    pagamento: document.getElementById('form-pagamento').value.trim(),
    validade: document.getElementById('form-validade').value,
    solicitacao: document.getElementById('form-solicitacao').value.trim(),
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
    // Mensagem mais clara para conflito de duplicata
    let msg = err.message || 'Erro ao salvar credor';
    if (msg.includes('Já existe um credor ativo com este nome')) {
      msg = `⚠️ Já existe outro credor cadastrado com o nome "${nome}". Altere o nome antes de salvar.`;
    } else if (msg.includes('Já existe um credor ativo com este CNPJ')) {
      msg = `⚠️ Já existe outro credor cadastrado com este CNPJ. Verifique o CNPJ informado.`;
    }
    showToast(msg, 'error');
    console.error(err);
  } finally {
    setLoading(false);
  }
}

async function onDeleteCredor(idVal = null) {
  const parsedId = idVal !== null ? idVal : parseInt(document.getElementById('form-id').value, 10);
  const effectiveId = Number.isNaN(parsedId) ? pendingDeleteCredorId : parsedId;
  if (!effectiveId) return;
  try {
    setLoading(true);
    await apiDelete(`/credores/${effectiveId}`);
    await loadCredores();
    delete state.empenhados[effectiveId];
    invalidateFilterCache();
    closeModal();
    render();
    showToast('Credor removido', 'info');
  } catch (err) {
    showToast(err.message || 'Erro ao remover', 'error');
  } finally {
    setLoading(false);
    pendingDeleteCredorId = null;
  }
}

// ── Duplicar Credor ───────────────────────────────────────────
async function duplicateCredor(c) {
  if (!confirm(`Duplicar o credor "${c.nome}"?\n\nUma cópia será criada com o nome "CÓPIA – ${c.nome}".
Você poderá editar a cópia em seguida.`)) return;
  try {
    setLoading(true);
    const novo = await apiPost(`/credores/${c.id}/duplicate`, {});
    await loadCredores();
    render();
    showToast(`✓ Credor duplicado: ${novo.nome}`, 'success');
    // Abre o modal de edição do novo credor para o usuário ajustar o nome
    setTimeout(() => openModal(novo.id), 200);
  } catch (err) {
    showToast(err.message || 'Erro ao duplicar credor', 'error');
    console.error(err);
  } finally {
    setLoading(false);
  }
}

// ── Loading Overlay ───────────────────────────────────────────
function isValidCnpj(value) {
  const digits = String(value || '').replace(/\D+/g, '');
  if (digits.length !== 14) return false;
  if (/^(\d)\1{13}$/.test(digits)) return false;

  const nums = digits.split('').map(Number);
  const weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const sum1 = nums.slice(0, 12).reduce((acc, n, i) => acc + n * weights1[i], 0);
  const rem1 = sum1 % 11;
  const dv1 = rem1 < 2 ? 0 : 11 - rem1;
  if (nums[12] !== dv1) return false;

  const weights2 = [6].concat(weights1);
  const sum2 = nums.slice(0, 12).reduce((acc, n, i) => acc + n * weights2[i], 0) + dv1 * weights2[12];
  const rem2 = sum2 % 11;
  const dv2 = rem2 < 2 ? 0 : 11 - rem2;
  return nums[13] === dv2;
}

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
    else if (action === 'duplicate') duplicateCredor(credor);
    else if (action === 'print') printCredor(credor);
  });

  document.getElementById('btn-prev-month').addEventListener('click', async () => {
    if (state.month === 0) { state.month = 11; state.year--; }
    else state.month--;
    state.page = 1;
    setLoading(true);
    await loadMonth();
    await loadCredores();
    setLoading(false);
    render();
  });

  document.getElementById('btn-next-month').addEventListener('click', async () => {
    if (state.month === 11) { state.month = 0; state.year++; }
    else state.month++;
    state.page = 1;
    setLoading(true);
    await loadMonth();
    await loadCredores();
    setLoading(false);
    render();
  });

  document.getElementById('search-input').addEventListener('input', e => {
    const nextValue = e.target.value;
    clearTimeout(_searchDebounceTimer);
    _searchDebounceTimer = setTimeout(async () => {
      state.searchTerm = nextValue;
      state.page = 1;
      setLoading(true);
      try {
        await loadCredores();
        render();
      } finally {
        setLoading(false);
      }
    }, 120);
  });

  function debouncedLoadCredores(delay = 300) {
    clearTimeout(_filterDebounceTimer);
    _filterDebounceTimer = setTimeout(async () => {
      setLoading(true);
      try {
        await loadCredores();
        render();
      } finally {
        setLoading(false);
      }
    }, delay);
  }

  document.getElementById('filter-dept').addEventListener('change', e => {
    state.filterDept = e.target.value;
    state.page = 1;
    const deptBtns = document.querySelectorAll('.dept-stat-btn');
    deptBtns.forEach(b => b.classList.remove('active-dept'));
    if (state.filterDept) {
      const btn = document.querySelector(`.dept-stat-btn[data-dept="${state.filterDept}"]`);
      if (btn) btn.classList.add('active-dept');
    }
    debouncedLoadCredores();
  });

  document.getElementById('filter-status').addEventListener('change', e => {
    state.filterStatus = e.target.value;
    state.page = 1;
    debouncedLoadCredores();
  });

  document.getElementById('filter-tipo').addEventListener('change', e => {
    state.filterTipo = e.target.value;
    state.page = 1;
    debouncedLoadCredores();
  });

  document.getElementById('filter-cadastro').addEventListener('change', e => {
    state.filterCadastro = e.target.value;
    state.page = 1;
    debouncedLoadCredores();
  });

  document.getElementById('filter-vencimento').addEventListener('change', e => {
    state.filterVencimento = e.target.value;
    state.page = 1;
    debouncedLoadCredores();
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
    openDeleteConfirmModal();
    return;
    if (confirm('Tem certeza que deseja remover este credor?')) {
      const password = prompt('Digite a senha de administrador para confirmar a exclusão:');
      if (password === '1999') {
        onDeleteCredor();
      } else if (password !== null) {
        showToast('Senha incorreta', 'error');
      }
    }
  });

  document.getElementById('delete-confirm-close').addEventListener('click', closeDeleteConfirmModal);
  document.getElementById('btn-delete-confirm-cancel').addEventListener('click', closeDeleteConfirmModal);
  document.getElementById('delete-confirm-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('delete-confirm-overlay')) closeDeleteConfirmModal();
  });
  document.getElementById('btn-delete-confirm-ok').addEventListener('click', async () => {
    if (pendingDeleteCredorId === null) return;
    const credor = state.credores.find(x => x.id === pendingDeleteCredorId);
    const nomeCredor = credor?.nome || getCurrentCredorName();
    const deleteId = pendingDeleteCredorId;
    closeDeleteConfirmModal();
    const password = prompt(`Digite a senha de administrador para confirmar a exclusão de ${nomeCredor}:`);
    if (password === '1999') {
      await onDeleteCredor(deleteId);
    } else if (password !== null) {
      showToast('Senha incorreta', 'error');
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      const deleteModal = document.getElementById('delete-confirm-overlay');
      if (deleteModal.classList.contains('open')) closeDeleteConfirmModal();
      else closeModal();
    }
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
      state.page = 1;
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

  document.getElementById('btn-page-prev').addEventListener('click', async () => {
    if (state.page <= 1) return;
    state.page -= 1;
    setLoading(true);
    try {
      await loadCredores();
      render();
    } finally {
      setLoading(false);
    }
  });

  document.getElementById('btn-page-next').addEventListener('click', async () => {
    if (state.page >= state.totalPages) return;
    state.page += 1;
    setLoading(true);
    try {
      await loadCredores();
      render();
    } finally {
      setLoading(false);
    }
  });

  document.getElementById('btn-export-csv').addEventListener('click', exportCSV);
  document.getElementById('btn-empenhar-todos')?.addEventListener('click', batchEmpenhar);

  // Lixeira
  document.getElementById('btn-lixeira').addEventListener('click', openLixeira);
  document.getElementById('lixeira-close').addEventListener('click', closeLixeira);
  document.getElementById('lixeira-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('lixeira-overlay')) closeLixeira();
  });

} // fim de attachEvents

// ── Lixeira de Credores ───────────────────────────────────────
function closeLixeira() {
  const el = document.getElementById('lixeira-overlay');
  el.classList.remove('open');
}

async function openLixeira() {
  const overlay = document.getElementById('lixeira-overlay');
  overlay.style.display = 'flex';
  overlay.classList.add('open');
  await loadLixeira();
}

async function loadLixeira() {
  const list = document.getElementById('lixeira-list');
  const empty = document.getElementById('lixeira-empty');
  const countEl = document.getElementById('lixeira-count');
  list.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-3);font-size:13px;">Carregando...</div>';
  empty.style.display = 'none';
  try {
    const rows = await apiGet('/credores/deletados');
    countEl.textContent = rows.length ? `(${rows.length})` : '';
    if (!rows.length) {
      list.innerHTML = '';
      empty.style.display = 'block';
      return;
    }
    list.innerHTML = rows.map(c => {
      const dept = c.departamento || '—';
      const valor = c.valor ? formatBRL(c.valor) : '—';
      const deletadoEm = c.atualizado_em ? new Date(c.atualizado_em).toLocaleDateString('pt-BR') : '—';
      return `
        <div class="lixeira-item" data-id="${c.id}" style="
          display:flex; align-items:center; gap:14px; padding:14px 20px;
          border-bottom:1px solid var(--border); font-size:13px;
        ">
          <div style="flex:1; min-width:0;">
            <div style="font-weight:700; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${c.nome}</div>
            <div style="color:var(--text-3); font-size:11px; margin-top:2px;">${dept} · ${valor} · Excluído em ${deletadoEm}</div>
            ${c.cnpj ? `<div style="color:var(--text-3);font-size:11px;">${c.cnpj}</div>` : ''}
          </div>
          <button onclick="restaurarCredor(${c.id}, this)" style="
            flex-shrink:0; padding:6px 14px; border-radius:var(--radius-sm);
            border:none; background:var(--green-bg); color:var(--green-dark);
            font-size:12px; font-weight:600; cursor:pointer; font-family:inherit;
            transition:opacity 0.15s;
          ">↩ Restaurar</button>
        </div>`;
    }).join('');
  } catch (err) {
    list.innerHTML = `<div style="padding:24px;text-align:center;color:var(--red);font-size:13px;">${err.message}</div>`;
  }
}

async function restaurarCredor(id, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  try {
    const res = await fetch(API + `/credores/${id}/restaurar`, { method: 'PUT' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erro ao restaurar');
    showToast(`✓ ${data.credor.nome} restaurado`, 'success');
    await loadLixeira();
    await loadCredores();
    render();
  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.textContent = '↩ Restaurar';
  }
}

// ── Init ──────────────────────────────────────────────────────
async function init() {
  try {
    attachEvents();
    const startsOnHome = document.body.classList.contains('home-page');
    if (!startsOnHome) {
      await ensureMainAppLoaded();
    }
  } catch (err) {
    console.error('Falha ao conectar com o servidor:', err);
    document.getElementById('empenhos-grid').innerHTML = `
          <div style="grid-column:1/-1; text-align:center; padding:60px 20px; color:#f87171;">
            <p style="font-size:18px; font-weight:700; margin-bottom:10px;">⚠️ Servidor não encontrado</p>
            <p style="color:#94a3b8;">Inicie o servidor clicando duas vezes em <strong>iniciar.bat</strong></p>
          </div>`;
    document.getElementById('empty-state').style.display = 'none';
  } finally {}
}

// ── Theme Toggle ───────────────────────────────────────────────
function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else if (saved === 'vintage') {
    document.documentElement.setAttribute('data-theme', 'vintage');
  } else if (saved === 'cosmos') {
    document.documentElement.setAttribute('data-theme', 'cosmos');
  } else if (saved === 'esmeralda') {
    document.documentElement.setAttribute('data-theme', 'esmeralda');
  } else if (saved === 'diamante') {
    document.documentElement.setAttribute('data-theme', 'diamante');
  } else if (saved === 'safira') {
    document.documentElement.setAttribute('data-theme', 'safira');
  } else if (saved === 'vulcano') {
    document.documentElement.setAttribute('data-theme', 'vulcano');
  } else if (saved === 'crepusculo') {
    document.documentElement.setAttribute('data-theme', 'crepusculo');
  } else if (saved === 'nordico') {
    document.documentElement.setAttribute('data-theme', 'nordico');
  } else if (saved === 'cacau') {
    document.documentElement.setAttribute('data-theme', 'cacau');
  } else if (saved === 'ametista') {
    document.documentElement.setAttribute('data-theme', 'ametista');
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
  else if (current === 'vintage') label.textContent = 'Tema Cosmos';
  else if (current === 'cosmos') label.textContent = 'Tema Esmeralda';
  else if (current === 'esmeralda') label.textContent = 'Tema Diamante';
  else if (current === 'diamante') label.textContent = 'Tema Safira';
  else if (current === 'safira') label.textContent = 'Tema Vulcano';
  else if (current === 'vulcano') label.textContent = 'Tema Crepúsculo';
  else if (current === 'crepusculo') label.textContent = 'Tema Nórdico';
  else if (current === 'nordico') label.textContent = 'Tema Cacau';
  else if (current === 'cacau') label.textContent = 'Tema Ametista';
  else if (current === 'ametista') label.textContent = 'Tema Claro';
}

function initCosmosEffects() {
  if (window.__cosmosEffectsInitialized) return;
  window.__cosmosEffectsInitialized = true;

  const state = {
    timer: null,
    observer: null,
  };

  function isCosmosTheme() {
    return document.documentElement.getAttribute('data-theme') === 'cosmos';
  }

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function clearTimer() {
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }
  }

  function createComet() {
    if (!isCosmosTheme() || prefersReducedMotion() || document.hidden) return;

    const comet = document.createElement('div');
    comet.className = 'cosmic-comet';

    const fromLeft = Math.random() > 0.45;
    const startX = fromLeft ? -220 : window.innerWidth + 220;
    const startY = Math.round(window.innerHeight * (0.06 + Math.random() * 0.34));
    const moveX = fromLeft ? window.innerWidth + 420 : -(window.innerWidth + 420);
    const moveY = Math.round(window.innerHeight * (0.14 + Math.random() * 0.22));
    const angle = fromLeft ? `${8 + Math.random() * 9}deg` : `${172 - Math.random() * 9}deg`;
    const duration = `${3.6 + Math.random() * 2.8}s`;

    comet.style.setProperty('--startX', `${startX}px`);
    comet.style.setProperty('--startY', `${startY}px`);
    comet.style.setProperty('--moveX', `${moveX}px`);
    comet.style.setProperty('--moveY', `${moveY}px`);
    comet.style.setProperty('--angle', angle);
    comet.style.setProperty('--duration', duration);
    comet.style.setProperty('--comet-length', `${80 + Math.round(Math.random() * 60)}px`);

    comet.addEventListener('animationend', () => comet.remove(), { once: true });
    document.body.appendChild(comet);
  }

  function scheduleNextComet() {
    clearTimer();
    if (!isCosmosTheme() || prefersReducedMotion()) return;
    const delay = 8000 + Math.random() * 10000;
    state.timer = window.setTimeout(() => {
      createComet();
      scheduleNextComet();
    }, delay);
  }

  function syncCosmosEffects() {
    if (!document.body) return;
    document.body.classList.toggle('cosmos-active', isCosmosTheme());
    if (isCosmosTheme()) scheduleNextComet();
    else clearTimer();
  }

  state.observer = new MutationObserver(syncCosmosEffects);
  state.observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimer();
    else syncCosmosEffects();
  });

  syncCosmosEffects();
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
  } else if (current === 'vintage') {
    html.setAttribute('data-theme', 'cosmos');
    localStorage.setItem('theme', 'cosmos');
  } else if (current === 'cosmos') {
    html.setAttribute('data-theme', 'esmeralda');
    localStorage.setItem('theme', 'esmeralda');
  } else if (current === 'esmeralda') {
    html.setAttribute('data-theme', 'diamante');
    localStorage.setItem('theme', 'diamante');
  } else if (current === 'diamante') {
    html.setAttribute('data-theme', 'safira');
    localStorage.setItem('theme', 'safira');
  } else if (current === 'safira') {
    html.setAttribute('data-theme', 'vulcano');
    localStorage.setItem('theme', 'vulcano');
  } else if (current === 'vulcano') {
    html.setAttribute('data-theme', 'crepusculo');
    localStorage.setItem('theme', 'crepusculo');
  } else if (current === 'crepusculo') {
    html.setAttribute('data-theme', 'nordico');
    localStorage.setItem('theme', 'nordico');
  } else if (current === 'nordico') {
    html.setAttribute('data-theme', 'cacau');
    localStorage.setItem('theme', 'cacau');
  } else if (current === 'cacau') {
    html.setAttribute('data-theme', 'ametista');
    localStorage.setItem('theme', 'ametista');
  } else {
    html.removeAttribute('data-theme');
    localStorage.setItem('theme', 'light');
  }
}

function initAppDOM() {
  initTheme();
  initCosmosEffects();
  if (typeof initAvatarCheckBadges === 'function') {
    initAvatarCheckBadges();
  }
  if (typeof initSpotlightCards === 'function') {
    initSpotlightCards();
  }
  syncThemeLabel();
  const syncExtraThemeLabels = () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    let text = 'Tema Escuro';
    if (current === 'dark') text = 'Tema Vintage';
    if (current === 'vintage') text = 'Tema Cosmos';
    if (current === 'cosmos') text = 'Tema Esmeralda';
    if (current === 'esmeralda') text = 'Tema Diamante';
    if (current === 'diamante') text = 'Tema Safira';
    if (current === 'safira') text = 'Tema Vulcano';
    if (current === 'vulcano') text = 'Tema Crepúsculo';
    if (current === 'crepusculo') text = 'Tema Nórdico';
    if (current === 'nordico') text = 'Tema Cacau';
    if (current === 'cacau') text = 'Tema Ametista';
    if (current === 'ametista') text = 'Tema Claro';
    
    const sidebarLabel = document.querySelector('.theme-label-sidebar');
    if (sidebarLabel) sidebarLabel.textContent = text;
    const mobileLabel = document.querySelector('.theme-label-mobile');
    if (mobileLabel) mobileLabel.textContent = text;
    
    // Sync BB-8 checkbox state
    const cb = document.getElementById('bb8-theme-checkbox');
    if (cb) {
      cb.checked = (current !== 'light');
    }
  };
  syncExtraThemeLabels();

  const syncThemeButtons = () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    document.querySelectorAll('.theme-select-btn').forEach(btn => {
      const val = btn.getAttribute('data-theme-val');
      if (val === current) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  };
  syncThemeButtons();

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.theme-select-btn');
    if (btn) {
      const val = btn.getAttribute('data-theme-val');
      if (val === 'light') {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('theme', 'light');
      } else {
        document.documentElement.setAttribute('data-theme', val);
        localStorage.setItem('theme', val);
      }
      syncThemeButtons();
      syncExtraThemeLabels();
    }
  });


  // Global dynamic glow tracking for buttons and cards on dashboard
  document.addEventListener('mousemove', (e) => {
    const el = e.target.closest('[data-glow-btn], .hs-card');
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    el.style.setProperty('--glow-x', `${x}px`);
    el.style.setProperty('--glow-y', `${y}px`);
  });
  
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
  document.getElementById('bb8-theme-checkbox')?.addEventListener('change', (e) => {
    if (e.target.checked) {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
    }
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
    const icon = document.getElementById('sidebar-expand-icon');
    if (!btn || !label) return;
    const sidebarGroups = document.querySelectorAll('.nav-group-sidebar');
    const allOpen = [...sidebarGroups].every(g => g.classList.contains('open'));
    if (allOpen) {
      label.textContent = 'Recolher tudo';
      btn.classList.add('expanded');
      if (icon) icon.style.transform = 'rotate(180deg)';
    } else {
      label.textContent = 'Expandir tudo';
      btn.classList.remove('expanded');
      if (icon) icon.style.transform = 'rotate(0deg)';
    }
  }

  // Sincroniza o estado inicial do botão
  syncSidebarExpandBtn();

  const btnSidebarExpandAll = document.getElementById('btn-sidebar-expand-all');
  if (btnSidebarExpandAll) {
    btnSidebarExpandAll.addEventListener('click', () => {
      const sidebarGroups = document.querySelectorAll('.nav-group-sidebar');
      const allOpen = [...sidebarGroups].every(g => g.classList.contains('open'));
      sidebarGroups.forEach(g => {
        g.classList.toggle('open', !allOpen);
        const toggleBtn = g.querySelector('.sidebar-group-toggle');
        if (toggleBtn) toggleBtn.setAttribute('aria-expanded', !allOpen ? 'true' : 'false');
      });
      syncSidebarExpandBtn();
    });
  }

  // Nav group dropdowns (Documentos / Financeiro / Ferramentas)
  document.querySelectorAll('.nav-group-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const group = btn.closest('.nav-group');
      if (!group) return;
      const isSidebar = group.classList.contains('nav-group-sidebar');

      if (isSidebar) {
        // Na sidebar: toggle independente (não fecha os outros)
        group.classList.toggle('open');
        const isOpen = group.classList.contains('open');
        btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
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
  
  // ADM Authentication — restored from session on page load
  let isAdmAuthenticated = sessionStorage.getItem('adm_auth') === '1';
  
  // Atualizar info do usuario no header
  var userNome = sessionStorage.getItem('user_nome');
  var userNivel = sessionStorage.getItem('user_nivel');
  var nomeEl = document.getElementById('header-usuario-nome');
  var adminBtns = document.querySelectorAll('[data-nivel="admin"]');
  if (userNome && nomeEl) nomeEl.textContent = userNome;
  if (userNivel !== 'admin') {
    adminBtns.forEach(function(el){ el.style.display = 'none'; });
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

  async function handleTabClick(tabName, requiresAuth) {
    if (requiresAuth) {
      var nivel = sessionStorage.getItem('user_nivel');
      if (nivel !== 'admin') {
        window.location.href = '/login.html';
        return;
      }
    }
    if (tabName !== 'adm') {
      await ensureMainAppLoaded();
    }
    setActiveTab(tabName);
    if (tabName === 'adm') {
      showAdmPanel();
    } else {
      hideAdmPanel();
    }
    // Garante que a área de credores seja exibida ao navegar pela sidebar
    if (typeof window.showCredoresArea === 'function') {
      window.showCredoresArea();
    }
  }
  
  // Desktop nav tabs
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const tabName = tab.dataset.tab;
      if (!tabName) return;
      const nivelRequerido = tab.dataset.nivel;
      if (nivelRequerido && sessionStorage.getItem('user_nivel') !== nivelRequerido) {
        window.location.href = '/login.html';
        return;
      }
      handleTabClick(tabName, false);
    });
  });
  
  // Mobile nav items
  document.querySelectorAll('.mobile-nav-item[data-tab]').forEach(item => {
    item.addEventListener('click', () => {
      const tabName = item.dataset.tab;
      const nivelRequerido = item.dataset.nivel;
      if (nivelRequerido && sessionStorage.getItem('user_nivel') !== nivelRequerido) {
        window.location.href = '/login.html';
        return;
      }
      handleTabClick(tabName, false);
      closeMobileNav();
    });
  });
  
  // ADM logout
  document.getElementById('adm-logout')?.addEventListener('click', async () => {
    await fetch('/api/auth/sair', { method: 'POST' }).catch(() => {});
    sessionStorage.removeItem('adm_auth');
    sessionStorage.removeItem('user_nome');
    sessionStorage.removeItem('user_nivel');
    window.location.href = '/login.html';
  });
  document.getElementById('header-logout-btn')?.addEventListener('click', async () => {
    await fetch('/api/auth/sair', { method: 'POST' }).catch(() => {});
    sessionStorage.clear();
    window.location.href = '/login.html';
  });
  
  init().then(() => {
    // Auto-open ADM tab when navigated via /#adm
    if (window.location.hash === '#adm') {
      window.location.hash = '';
      document.querySelector('.nav-tab[data-tab="adm"]')?.click();
    }
  });

  // Auto-apply animated glowing search bars to search/filter fields
  if (typeof applyGlowingSearchBars === 'function') {
    applyGlowingSearchBars();
  }
}

function applyGlowingSearchBars() {
  const inputs = document.querySelectorAll('input[type="text"], input[type="search"]');
  inputs.forEach(input => {
    if (input.classList.contains('glowing-search-input')) return;
    
    const placeholder = (input.placeholder || '').toLowerCase();
    const id = (input.id || '').toLowerCase();
    const className = (input.className || '').toLowerCase();
    
    // Do not wrap comment inputs
    if (
      id.includes('comment') || 
      className.includes('comment') || 
      placeholder.includes('coment')
    ) {
      return;
    }
    
    if (
      placeholder.includes('buscar') ||
      placeholder.includes('pesquisar') ||
      placeholder.includes('busca') ||
      placeholder.includes('filtro') ||
      placeholder.includes('filtrar') ||
      placeholder.includes('pesquisa') ||
      id.includes('search') ||
      id.includes('busca') ||
      id.includes('filtro') ||
      className.includes('search') ||
      className.includes('filtro')
    ) {
      const container = document.createElement('div');
      container.className = 'glowing-search-container';
      
      const poda = document.createElement('div');
      poda.className = 'glowing-search-poda';
      
      poda.innerHTML = `
        <div class="glow-layer-1"></div>
        <div class="glow-layer-2"></div>
        <div class="glow-layer-3"></div>
        <div class="glow-layer-4"></div>
        <div class="glowing-search-main">
          <div class="glowing-search-mask-pink"></div>
          <div class="glowing-search-right-glow"></div>
          <div class="glowing-search-icon-filter">
            <svg preserveAspectRatio="none" height="18" width="18" viewBox="4.8 4.56 14.832 15.408" fill="none">
              <path d="M8.16 6.65002H15.83C16.47 6.65002 16.99 7.17002 16.99 7.81002V9.09002C16.99 9.56002 16.7 10.14 16.41 10.43L13.91 12.64C13.56 12.93 13.33 13.51 13.33 13.98V16.48C13.33 16.83 13.1 17.29 12.81 17.47L12 17.98C11.24 18.45 10.2 17.92 10.2 16.99V13.91C10.2 13.5 9.97 12.98 9.73 12.69L7.52 10.36C7.23 10.08 7 9.55002 7 9.20002V7.87002C7 7.17002 7.52 6.65002 8.16 6.65002Z" stroke="#d6d6e6" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
          </div>
          <div class="glowing-search-icon-left">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </div>
        </div>
      `;
      
      input.classList.add('glowing-search-input');
      
      const parent = input.parentNode;
      parent.insertBefore(container, input);
      container.appendChild(poda);
      const mainDiv = poda.querySelector('.glowing-search-main');
      mainDiv.insertBefore(input, mainDiv.firstChild);
    }
  });
}

/* ── Auto-injetor de status check badges para avatares ── */
function initAvatarCheckBadges() {
  const selector = '.mural-user-avatar, .mural-card-assignee-avatar, .mural-filter-avatar, .kb-avatar';
  
  const initial = document.querySelectorAll(selector);
  initial.forEach(avatar => {
    if (!avatar.querySelector('.avatar-badge-check')) {
      const badge = document.createElement('span');
      badge.className = 'avatar-badge-check';
      avatar.appendChild(badge);
    }
  });

  if (window._avatarObserver) {
    window._avatarObserver.disconnect();
  }
  
  const observer = new MutationObserver(mutations => {
    mutations.forEach(mutation => {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        const avatars = node.querySelectorAll(selector);
        avatars.forEach(avatar => {
          if (!avatar.querySelector('.avatar-badge-check')) {
            const badge = document.createElement('span');
            badge.className = 'avatar-badge-check';
            avatar.appendChild(badge);
          }
        });
        
        if (node.classList && (
          node.classList.contains('mural-user-avatar') || 
          node.classList.contains('mural-card-assignee-avatar') || 
          node.classList.contains('mural-filter-avatar') || 
          node.classList.contains('kb-avatar')
        )) {
          if (!node.querySelector('.avatar-badge-check')) {
            const badge = document.createElement('span');
            badge.className = 'avatar-badge-check';
            node.appendChild(badge);
          }
        }
      });
    });
  });

  observer.observe(document.body, { childList: true, subtree: true });
  window._avatarObserver = observer;
}

/* ── Sincronização do efeito spotlight-card (hover brilhante) ── */
function initSpotlightCards() {
  const syncPointer = (e) => {
    const { clientX: x, clientY: y } = e;
    const cards = document.querySelectorAll('[data-glow]');
    cards.forEach(card => {
      card.style.setProperty('--x', x.toFixed(2));
      card.style.setProperty('--xp', (x / window.innerWidth).toFixed(2));
      card.style.setProperty('--y', y.toFixed(2));
      card.style.setProperty('--yp', (y / window.innerHeight).toFixed(2));
    });
  };
  document.addEventListener('pointermove', syncPointer);
}


if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAppDOM);
} else {
  initAppDOM();
}
