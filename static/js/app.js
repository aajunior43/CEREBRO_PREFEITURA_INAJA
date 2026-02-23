/* ============================================================
   app.js – Controle de Empenhos Mensais (versão Flask+SQLite)
   Prefeitura Municipal de Inajá
   ============================================================ */
'use strict';

// ── Constantes ─────────────────────────────────────────────
const API = `http://${window.location.hostname}:5000/api`;

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
  expandAll: false,
  credores: [],
  empenhados: {},
};

// ── API Calls ────────────────────────────────────────────────
async function apiGet(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${path} → ${r.status}`);
  return r.json();
}

async function apiPut(path, body) {
  const r = await fetch(API + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`PUT ${path} → ${r.status}`);
  return r.json();
}

async function apiDelete(path) {
  const r = await fetch(API + path, { method: 'DELETE' });
  if (!r.ok) throw new Error(`DELETE ${path} → ${r.status}`);
  return r.json();
}

// ── Carregar dados do mês ────────────────────────────────────
async function loadMonth() {
  const m = state.month + 1;
  const [empList] = await Promise.all([
    apiGet(`/empenhos/${state.year}/${m}`),
  ]);
  state.empenhados = {};
  empList.forEach(e => {
    state.empenhados[e.credor_id] = true;
  });
}

// ── Helpers de formatação ────────────────────────────────────
function formatBRL(value) {
  if (!value || value === 0) return 'A definir';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL',
  }).format(value);
}

// ── Render ───────────────────────────────────────────────────
function render() {
  renderMonthNav();
  renderCards();
  renderStats();
}

function renderMonthNav() {
  document.getElementById('current-month-name').textContent = MESES[state.month];
  document.getElementById('current-month-year').textContent = state.year;
}

function filteredCredores() {
  return state.credores.filter(c => {
    const name = (c.nome || '').toLowerCase();
    const search = state.searchTerm.toLowerCase();
    if (search &&
      !name.includes(search) &&
      !(c.descricao || '').toLowerCase().includes(search) &&
      !(c.cnpj || '').toLowerCase().includes(search)) return false;
    if (state.filterDept && (c.departamento || '') !== state.filterDept) return false;
    if (state.filterStatus) {
      const done = !!state.empenhados[c.id];
      if (state.filterStatus === 'empenhado' && !done) return false;
      if (state.filterStatus === 'pendente' && done) return false;
    }
    return true;
  });
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

  list.forEach((c, idx) => {
    const done = !!state.empenhados[c.id];
    grid.appendChild(buildCard(c, done, idx));
  });
}

function buildCard(c, done, idx) {
  const div = document.createElement('div');
  div.className = `empenho-card${done ? ' done' : ''}${state.expandAll ? ' expanded' : ''}`;
  div.dataset.id = c.id;
  div.style.animationDelay = `${Math.min(idx, 20) * 25}ms`;

  const dept = c.departamento || '';
  const tipo = c.tipo_valor || 'FIXO';
  const valor = c.valor || 0;
  const obs = c.obs || '';
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
        <span class="card-name">${c.nome || '—'}${obs ? `<span class="badge-obs">${obs}</span>` : ''}</span>
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
        <button class="btn-expand" title="Ver detalhes">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6"/></svg>
        </button>
        <button class="btn-edit" title="Editar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </button>
        <button class="btn-print" title="Imprimir">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
        </button>
        <button class="btn-empenhar ${done ? 'done-btn' : 'pending'}">
          ${done ? '✓ Empenhado' : '○ Empenhar'}
        </button>
      </div>
    </div>
    <div class="card-details">
      ${c.cnpj ? `<div class="detail-row"><span class="detail-label">CNPJ</span><span class="detail-value">${c.cnpj}</span></div>` : ''}
      ${c.email ? `<div class="detail-row"><span class="detail-label">E-mail</span><span class="detail-value">${c.email}</span></div>` : ''}
      ${c.solicitacao ? `<div class="detail-row"><span class="detail-label">Solicitação</span><span class="detail-value">${c.solicitacao}</span></div>` : ''}
      ${c.pagamento ? `<div class="detail-row"><span class="detail-label">Pagamento</span><span class="detail-value">${c.pagamento} dias</span></div>` : ''}
    </div>
  `;

  div.querySelector('.btn-empenhar').addEventListener('click', async e => {
    e.stopPropagation();
    await onToggle(c.id, c.nome);
  });

  div.querySelector('.btn-expand').addEventListener('click', e => {
    e.stopPropagation();
    div.classList.toggle('expanded');
  });

  div.querySelector('.btn-edit').addEventListener('click', e => {
    e.stopPropagation();
    openModal(c.id);
  });

  div.querySelector('.btn-print').addEventListener('click', e => {
    e.stopPropagation();
    printCredor(c);
  });

  return div;
}

// ── Stats ─────────────────────────────────────────────────────
function renderStats() {
  const credores = state.credores;
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
}

// ── Template CSS compartilhado (print) ───────────────────────
function _printCSS() {
  return `
    @page { margin: 15mm 12mm; }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 13px;
      color: #2d3748;
      background: #fff;
    }

    /* ── Faixa superior ── */
    .doc-banner {
      background: linear-gradient(135deg, #1e3a5f 0%, #2d5986 100%);
      padding: 18px 28px 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-radius: 0;
    }
    .doc-banner-left { display:flex; flex-direction:row; align-items:center; gap:12px; }
    .doc-banner-brasao { height:64px; width:auto; object-fit:contain; filter:drop-shadow(0 1px 3px rgba(0,0,0,0.4)); }
    .doc-banner-text { display:flex; flex-direction:column; gap:2px; }
    .doc-banner h1 {
      font-size: 16px; font-weight: 900;
      color: #fff; letter-spacing: -0.3px;
    }
    .doc-banner p {
      font-size: 11px; color: rgba(255,255,255,0.65);
      font-weight: 500; margin-top: 2px;
    }
    .doc-banner-right { text-align: right; }
    .doc-ref {
      font-size: 10px; color: rgba(255,255,255,0.55);
      text-transform: uppercase; letter-spacing: 0.5px;
    }
    .doc-ref strong {
      display: block; font-size: 13px;
      color: rgba(255,255,255,0.92);
      font-weight: 700; margin-top: 2px;
    }
    .stamp-done {
      display: inline-block;
      border: 2px solid #4ade80;
      color: #4ade80;
      font-size: 10px; font-weight: 800;
      padding: 3px 10px; border-radius: 20px;
      letter-spacing: 0.5px;
      margin-top: 6px;
    }

    /* ── Título do documento ── */
    .doc-title-block {
      text-align: center;
      padding: 16px 28px 12px;
      border-bottom: 3px solid #1e3a5f;
      margin-bottom: 20px;
    }
    .doc-title-block h2 {
      font-size: 18px; font-weight: 900;
      color: #1e3a5f;
      text-transform: uppercase;
      letter-spacing: 2.5px;
    }
    .doc-title-block .doc-subtitle {
      font-size: 10px; color: #718096;
      margin-top: 4px; font-weight: 500;
      letter-spacing: 0.3px;
    }

    /* ── Corpo ── */
    .doc-body { padding: 0 28px 20px; }

    .section-title {
      font-size: 9px; font-weight: 700;
      color: #a0aec0; text-transform: uppercase;
      letter-spacing: 1px; margin-bottom: 8px;
      padding-bottom: 4px;
      border-bottom: 1px solid #e2e8f0;
    }

    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    tr { border-bottom: 1px solid #edf2f7; }
    tr:last-child { border-bottom: none; }
    td { padding: 8px 10px; vertical-align: top; }
    td.label {
      font-weight: 700; color: #4a5568;
      width: 34%; font-size: 10px;
      text-transform: uppercase; letter-spacing: 0.5px;
      background: #f7fafc;
      border-right: 3px solid #e2e8f0;
    }
    td.value { color: #2d3748; font-size: 13px; padding-left: 14px; }

    /* ── Caixa de valor ── */
    .valor-box {
      background: linear-gradient(135deg, #ebf8ff, #e6f2fb);
      border: 1px solid #bee3f8;
      border-left: 4px solid #3182ce;
      border-radius: 6px;
      padding: 12px 18px;
      margin-bottom: 20px;
      text-align: center;
    }
    .vb-label {
      font-size: 10px; font-weight: 700;
      color: #2c5282; text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .vb-value {
      font-size: 22px; font-weight: 900;
      color: #2b6cb0;
    }

    /* ── Data ── */
    .sign-date {
      font-size: 11px; color: #718096;
      text-align: center;
      margin-bottom: 28px;
      padding: 8px 0;
      border-top: 1px dashed #e2e8f0;
      border-bottom: 1px dashed #e2e8f0;
    }

    /* ── Rodapé ── */
    .doc-footer {
      background: #f7fafc;
      border-top: 2px solid #1e3a5f;
      padding: 8px 28px;
      display: flex;
      justify-content: space-between;
      font-size: 8px;
      color: #a0aec0;
      letter-spacing: 0.3px;
      margin-top: 28px;
    }
    .doc-footer strong { color: #718096; }

    /* ── Assinatura ── */
    .sign-section {
      display: flex;
      gap: 32px;
      justify-content: center;
    }
    .sign-block { text-align: center; }
    .sign-line-top {
      width: 350px;
      border-bottom: 1px solid #2d3748;
      margin: 0 auto 8px;
      padding-bottom: 4px;
    }
    .sign-label {
      font-size: 11px; font-weight: 700;
      color: #2d3748; letter-spacing: 0.2px;
    }
    .sign-sub { font-size: 9px; color: #718096; margin-top: 2px; }
  `;
}

// ── Bloco HTML de uma página de credor ───────────────────────
function _buildDocPage(c, done, mesNome, ano, isLast) {
  const isVar = (c.tipo_valor || '').toUpperCase().includes('VAR');
  const valorStr = (isVar && !c.valor) ? 'Valor variável' : formatBRL(c.valor || 0);
  const pb = isLast ? '' : 'page-break-after:always;';

  const campos = [
    ['Credor / Fornecedor', c.nome],
    ['Descrição do Serviço', c.descricao],
    ['Departamento', c.departamento],
    ['CNPJ', c.cnpj],
    ['E-mail', c.email],
    ['Tipo de Valor', c.tipo_valor],
    ['N.º Solicitação', c.solicitacao],
    ['Observações', c.obs],
  ].filter(([, v]) => v && String(v).trim());

  const tableRows = campos.map(([l, v]) =>
    `<tr><td class="label">${l}</td><td class="value">${v}</td></tr>`
  ).join('');

  return `
    <div style="${pb}">
      <div class="doc-banner">
        <div class="doc-banner-left">
          <img class="doc-banner-brasao" src="${typeof BRASAO_B64 !== 'undefined' ? BRASAO_B64 : ''}" alt="Bras&#227;o" />
          <div class="doc-banner-text">
            <h1>Prefeitura Municipal de Inaj&#225;</h1>
          </div>
        </div>
        <div class="doc-banner-right">
          <div class="doc-ref">Refer&#234;ncia<strong>${mesNome} / ${ano}</strong></div>
        </div>
      </div>

      <div class="doc-title-block">
        <h2>Solicita&#231;&#227;o de Fornecimento</h2>
      </div>

      <div class="doc-body">
        <div class="section-title">Dados do Fornecedor / Servi&#231;o</div>
        <table>${tableRows}</table>

        <div class="valor-box">
          <span class="vb-value">${valorStr}</span>
        </div>

        <div class="sign-date">
          Inaj&#225; &mdash; PR, &nbsp; _______ de &nbsp; __________________ de &nbsp; ${ano}
        </div>

        <div class="sign-section">
          <div class="sign-block">
            <div class="sign-line-top"></div>
            <div class="sign-label">Ordenador de Despesa</div>
            <div class="sign-sub">Prefeitura Municipal de Inaj&#225;</div>
          </div>
        </div>
      </div>

    </div>`;
}

// ── Imprimir Credor (individual) ──────────────────────────────
function printCredor(c) {
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

  const win = window.open('', '_blank', 'width=760,height=750');
  if (!win) {
    showToast('Bloqueador de popups ativado. Permita popups para imprimir.', 'error');
    return;
  }
  win.document.write(html);
  win.document.close();
}

// ── Imprimir em Lote ─────────────────────────────────────────
function printLote() {
  const lista = filteredCredores();
  if (lista.length === 0) { showToast('Nenhum credor para imprimir', 'error'); return; }

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
      const updated = await apiPut(`/credores/${idVal}`, payload);
      const idx = state.credores.findIndex(c => c.id === idVal);
      if (idx >= 0) state.credores[idx] = updated;
      showToast('Credor atualizado!', 'success');
    } else {
      const created = await apiPost('/credores', payload);
      state.credores.push(created);
      showToast('Credor adicionado!', 'success');
    }
    closeModal();
    render();
  } catch (err) {
    showToast('Erro ao salvar credor', 'error');
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
    state.credores = state.credores.filter(c => c.id !== idVal);
    delete state.empenhados[idVal];
    closeModal();
    render();
    showToast('Credor removido', 'info');
  } catch (err) {
    showToast('Erro ao remover', 'error');
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
  document.getElementById('btn-prev-month').addEventListener('click', async () => {
    if (state.month === 0) { state.month = 11; state.year--; }
    else state.month--;
    setLoading(true);
    await loadMonth();
    setLoading(false);
    render();
  });

  document.getElementById('btn-next-month').addEventListener('click', async () => {
    if (state.month === 11) { state.month = 0; state.year++; }
    else state.month++;
    setLoading(true);
    await loadMonth();
    setLoading(false);
    render();
  });

  document.getElementById('search-input').addEventListener('input', e => {
    state.searchTerm = e.target.value;
    renderCards();
  });

  document.getElementById('filter-dept').addEventListener('change', e => {
    state.filterDept = e.target.value;
    renderCards();
  });

  document.getElementById('filter-status').addEventListener('change', e => {
    state.filterStatus = e.target.value;
    renderCards();
  });

  document.getElementById('btn-expand-all').addEventListener('click', () => {
    state.expandAll = !state.expandAll;
    document.querySelectorAll('.empenho-card').forEach(c => c.classList.toggle('expanded', state.expandAll));
    const btn = document.getElementById('btn-expand-all');
    const svgExpand = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>`;
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
  document.getElementById('btn-logs').addEventListener('click', async () => {
    const overlay = document.getElementById('logs-overlay');
    const list = document.getElementById('logs-list');
    overlay.style.display = 'flex';
    overlay.classList.add('open');
    list.innerHTML = '<div class="spinner" style="margin: 20px auto;"></div>';
    try {
      const logs = await apiGet('/logs');
      if (logs.length === 0) {
        list.innerHTML = '<p style="text-align:center;color:var(--text-3);padding:20px;">Nenhum registro encontrado.</p>';
      } else {
        list.innerHTML = logs.map(log => {
          const iconMap = { 'CRIAR': '+', 'EDITAR': '✎', 'EXCLUIR': '×' };
          return `
            <div class="log-item">
              <div class="log-icon ${log.acao.toLowerCase()}">${iconMap[log.acao] || '•'}</div>
              <div class="log-content">
                <div class="log-acao">${log.acao}</div>
                <div class="log-nome">${log.credor_nome || '-'}</div>
                <div class="log-detalhes">${log.detalhes || ''}</div>
              </div>
              <div class="log-data">${log.data ? new Date(log.data).toLocaleString('pt-BR') : '-'}</div>
            </div>
          `;
        }).join('');
      }
    } catch (e) {
      list.innerHTML = '<p style="text-align:center;color:var(--red);padding:20px;">Erro ao carregar logs.</p>';
    }
  });

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
}

// ── Init ──────────────────────────────────────────────────────
async function init() {
  setLoading(true);
  try {
    attachEvents();
    const [credores] = await Promise.all([
      apiGet('/credores'),
      loadMonth(),
    ]);
    state.credores = credores;
    render();
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
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
}

function syncThemeLabel() {
  const label = document.querySelector('.theme-label');
  if (!label) return;
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  label.textContent = isDark ? 'Tema Claro' : 'Tema Escuro';
}

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  if (isDark) {
    html.removeAttribute('data-theme');
    localStorage.setItem('theme', 'light');
  } else {
    html.setAttribute('data-theme', 'dark');
    localStorage.setItem('theme', 'dark');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  syncThemeLabel();
  
  // Hamburger menu
  const hamburger = document.getElementById('hamburger');
  const mobileNav = document.getElementById('mobile-nav');
  const mobileOverlay = document.getElementById('mobile-nav-overlay');
  const mobileNavClose = document.getElementById('mobile-nav-close');
  
  function openMobileNav() {
    hamburger.classList.add('active');
    mobileNav.classList.add('open');
    mobileOverlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  
  function closeMobileNav() {
    hamburger.classList.remove('active');
    mobileNav.classList.remove('open');
    mobileOverlay.classList.remove('open');
    document.body.style.overflow = '';
  }
  
  hamburger.addEventListener('click', () => {
    if (mobileNav.classList.contains('open')) closeMobileNav();
    else openMobileNav();
  });
  
  mobileOverlay.addEventListener('click', closeMobileNav);
  mobileNavClose.addEventListener('click', closeMobileNav);
  
  // Mobile logs button
  document.getElementById('mobile-logs').addEventListener('click', () => {
    closeMobileNav();
    document.getElementById('btn-logs').click();
  });
  
  // Dropdown menu
  const dropdown = document.getElementById('dropdown-toggle').parentElement;
  document.getElementById('dropdown-toggle').addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('open');
  });
  document.addEventListener('click', () => dropdown.classList.remove('open'));

  // Nav group dropdowns (Documentos / Financeiro / Ferramentas)
  document.querySelectorAll('.nav-group-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const group = btn.closest('.nav-group');
      const isOpen = group.classList.contains('open');
      document.querySelectorAll('.nav-group').forEach(g => g.classList.remove('open'));
      if (!isOpen) group.classList.add('open');
    });
  });
  document.addEventListener('click', () =>
    document.querySelectorAll('.nav-group').forEach(g => g.classList.remove('open'))
  );
  
  // Theme toggle in dropdown
  document.getElementById('theme-toggle').addEventListener('click', () => {
    dropdown.classList.remove('open');
    toggleTheme();
    syncThemeLabel();
  });
  
  // ADM Authentication
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
  
  function checkPassword() {
    const password = document.getElementById('password-input').value;
    if (password === '1999') {
      isAdmAuthenticated = true;
      sessionStorage.setItem('adm_auth', '1');
      hidePasswordModal();
      // If redirected from another page, go back there
      const returnTo = sessionStorage.getItem('adm_return');
      if (returnTo) {
        sessionStorage.removeItem('adm_return');
        window.location.href = returnTo;
        return;
      }
      showAdmPanel();
      showToast('Bem-vindo à área administrativa!', 'success');
    } else {
      document.getElementById('password-error').style.display = 'block';
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
    isAdmAuthenticated = false;
  }
  
  // Handle tab clicks with auth requirement
  function setActiveTab(tabName) {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.mobile-nav-item[data-tab]').forEach(m => m.classList.remove('active'));
    document.querySelector(`.nav-tab[data-tab="${tabName}"]`)?.classList.add('active');
    document.querySelector(`.mobile-nav-item[data-tab="${tabName}"]`)?.classList.add('active');
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
  document.getElementById('password-close').addEventListener('click', hidePasswordModal);
  document.getElementById('password-submit').addEventListener('click', checkPassword);
  document.getElementById('password-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') checkPassword();
  });
  
  // ADM logout
  document.getElementById('adm-logout').addEventListener('click', () => {
    sessionStorage.removeItem('adm_auth');
    hideAdmPanel();
    document.querySelector('.nav-tab[data-tab="credores-fixos"]').click();
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
