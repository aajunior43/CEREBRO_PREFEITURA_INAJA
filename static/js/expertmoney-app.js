/**
 * ExpertMoney Analyzer v2.0 — Frontend App
 */
'use strict';

const API = `${window.location.origin}/api/extratos`;
const ACTIVE_ACCOUNT_KEY = 'expertmoney.activeAccountId';

// ── Local Folders Scanning (uploads/) ────────────────────────
async function scanLocalFolders() {
  const container = document.getElementById('local-folders-list');
  if (!container) return;
  try {
    const r = await fetch(`${API}/local-folders`);
    const folders = await r.json();
    if (!folders.length) {
      container.innerHTML = `
        <div style="grid-column: 1/-1; padding: 1.5rem; background: var(--bg-card); border: 1px dashed var(--border); border-radius: var(--radius); text-align: center;">
          <p style="color: var(--text-3); font-size: 0.875rem;">Nenhuma pasta de conta encontrada em 'uploads'.</p>
          <p style="color: var(--text-3); font-size: 0.75rem; margin-top: 0.25rem;">Crie subpastas com o número da conta dentro de <code>J:\\EXPERTMONEY\\uploads</code> para exibi-las aqui.</p>
        </div>`;
      return;
    }
    container.innerHTML = folders.map(folder => {
      return `
        <div class="zip-card">
          <span class="zip-card-title" title="${escHtml(folder.name)}">📂 Conta: ${escHtml(folder.name)}</span>
          <div style="font-size: 0.72rem; color: var(--text-2); margin-top: -0.25rem;">
            <span>Arquivos analíticos: <strong>${folder.fileCount}</strong></span>
          </div>
          <div class="zip-card-meta" style="margin-top: 0.25rem;">
            <span>OFX: ${folder.ofxCount}</span>
            <span>TXT: ${folder.txtCount}</span>
            <span>${fmtBytes(folder.size)}</span>
          </div>
          <div class="zip-card-actions">
            <button class="btn-primary btn-sm" onclick="loadLocalFolder('${escHtml(folder.name)}')">📥 Importar e Analisar</button>
          </div>
        </div>`;
    }).join('');
  } catch (err) {
    container.innerHTML = `<p style="color: var(--red); font-size: 0.875rem;">Erro ao listar pastas locais: ${err.message}</p>`;
  }
}

async function loadLocalFolder(folderName) {
  showLoader('Carregando arquivos da pasta local…', 20);
  try {
    const r = await fetch(`${API}/load-local-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folderName })
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error);

    state.sessionId = data.sessionId;
    renderFileList(data.files);
    document.getElementById('btn-clear').style.display = 'inline-flex';
    setStatusBadge('loading', `${data.fileCount} arquivo(s) prontos`);
    toast(`${data.fileCount} arquivo(s) carregados da pasta local`, 'success');
    setProgress(100);

    // Auto trigger analysis
    setTimeout(() => runAnalysis(), 500);
  } catch (err) {
    toast('Erro ao carregar pasta local: ' + err.message, 'error');
  } finally {
    hideLoader();
  }
}

async function runBatchAnalysis() {
  if (!confirm('Deseja iniciar a análise de todas as contas na pasta "uploads" em lote? Isso pode levar alguns segundos.')) return;
  showLoader('Iniciando análise em lote…', 10);
  try {
    setProgress(35);
    const r = await fetch(`${API}/analyze-batch`, { method: 'POST' });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error);

    setProgress(80);
    updateLoader('Atualizando painéis e menus…');
    
    // Refresh sidebar active accounts menu
    await updateActiveAccountsMenu();
    // Load accounts list if active
    if (document.getElementById('nav-accounts').classList.contains('active')) {
      await loadAccounts();
    }
    // Load history list if active
    if (document.getElementById('nav-history').classList.contains('active')) {
      await loadHistory();
    }

    setProgress(100);
    toast(`Análise concluída: ${data.totalAnalyzed} contas processadas!`, 'success');
    
    alert(`Análise em Lote Concluída!\n\n- Contas Processadas: ${data.totalAnalyzed}\n- Total de Alertas: ${data.totalAlerts} (${data.totalCritical}🔴 críticos, ${data.totalWarning}🟡 atenção)\n\nAs contas agora estão disponíveis no menu lateral "Contas Ativas" e podem ser inspecionadas individualmente clicando nelas.`);
  } catch (err) {
    toast('Erro na análise em lote: ' + err.message, 'error');
  } finally {
    hideLoader();
  }
}

// ── Local ZIP Scanning ───────────────────────────────────────
async function scanLocalZips() {
  const container = document.getElementById('local-zips-list');
  if (!container) return;
  try {
    const r = await fetch(`${API}/local-zips`);
    const zips = await r.json();
    if (!zips.length) {
      container.innerHTML = `
        <div style="grid-column: 1/-1; padding: 1.5rem; background: var(--bg-card); border: 1px dashed var(--border); border-radius: var(--radius); text-align: center;">
          <p style="color: var(--text-3); font-size: 0.875rem;">Nenhum arquivo .zip encontrado na pasta dedicada.</p>
          <p style="color: var(--text-3); font-size: 0.75rem; margin-top: 0.25rem;">Coloque arquivos ZIP diretamente em <code>J:\\EXPERTMONEY\\uploads_zip</code> para carregar aqui.</p>
        </div>`;
      return;
    }
    container.innerHTML = zips.map(zip => {
      let cardStyle = '';
      let badge = '';
      let actionBtn = `<button class="btn-primary btn-sm" onclick="loadLocalZip('${escHtml(zip.name)}')">📥 Carregar ZIP</button>`;
      
      if (zip.duplicate) {
        if (zip.recommended) {
          cardStyle = 'border-color: var(--green); box-shadow: 0 0 12px rgba(16, 185, 129, 0.2);';
          badge = `<span class="account-tag" style="background: rgba(16, 185, 129, 0.15); color: var(--green); font-size: 0.65rem; margin-bottom: 0.25rem; align-self: flex-start;">🌟 Recomendado (Mais Dados)</span>`;
        } else {
          cardStyle = 'border-color: var(--yellow); opacity: 0.7;';
          badge = `<span class="account-tag" style="background: rgba(245, 158, 11, 0.15); color: var(--yellow); font-size: 0.65rem; margin-bottom: 0.25rem; align-self: flex-start;">⚠️ Duplicado (Ignorar)</span>`;
          actionBtn = `<button class="btn-ghost btn-sm" onclick="loadLocalZip('${escHtml(zip.name)}')" title="${escHtml(zip.discardReason)}">📥 Forçar Carga</button>`;
        }
      }

      return `
        <div class="zip-card" style="${cardStyle}">
          ${badge}
          <span class="zip-card-title" title="${escHtml(zip.name)}">📦 ${escHtml(zip.name)}</span>
          <div style="font-size: 0.72rem; color: var(--text-2); margin-top: -0.25rem;">
            <span>Conta: <strong>${zip.account}</strong></span> • <span>Arquivos: ${zip.fileCount}</span>
          </div>
          <div class="zip-card-meta" style="margin-top: 0.25rem;">
            <span>${fmtBytes(zip.size)}</span>
            <span>${formatDateBR(zip.mtime)}</span>
          </div>
          ${zip.discardReason ? `<p style="font-size: 0.65rem; color: var(--yellow); line-height: 1.2; margin-top: 0.25rem;">${escHtml(zip.discardReason)}</p>` : ''}
          <div class="zip-card-actions">
            ${actionBtn}
          </div>
        </div>`;
    }).join('');
  } catch (err) {
    container.innerHTML = `<p style="color: var(--red); font-size: 0.875rem;">Erro ao listar arquivos ZIP: ${err.message}</p>`;
  }
}

async function loadLocalZip(filename) {
  showLoader('Carregando ZIP local…', 20);
  try {
    const r = await fetch(`${API}/load-local-zip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename })
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error);

    state.sessionId = data.sessionId;
    renderFileList(data.files);
    document.getElementById('btn-clear').style.display = 'inline-flex';
    setStatusBadge('loading', `${data.fileCount} arquivo(s) prontos`);
    toast(`${data.fileCount} arquivo(s) carregados do ZIP`, 'success');
    setProgress(100);

    // Auto trigger analysis
    setTimeout(() => runAnalysis(), 500);
  } catch (err) {
    toast('Erro ao carregar ZIP local: ' + err.message, 'error');
  } finally {
    hideLoader();
  }
}

// Auto-scan on load
document.addEventListener('DOMContentLoaded', () => {
  scanLocalFolders();
  scanLocalZips();
  updateActiveAccountsMenu();
  loadLatestSessionOnStart();
  initSearchSection();
});

async function loadLatestSessionOnStart() {
  try {
    const savedAccountId = localStorage.getItem(ACTIVE_ACCOUNT_KEY);
    const qs = savedAccountId ? `?accountId=${encodeURIComponent(savedAccountId)}` : '';
    const latestRes = await fetch(`${API}/latest-session${qs}`);
    if (latestRes.status === 404) return;
    const latest = await latestRes.json();
    if (!latestRes.ok) throw new Error(latest.error || 'Erro ao buscar a ultima sessao');

    const sessionRes = await fetch(`${API}/sessions/${latest.session.id}`);
    const data = await sessionRes.json();
    if (!sessionRes.ok) throw new Error(data.error || 'Erro ao carregar a ultima sessao');

    state.sessionId = latest.session.id;
    state.activeAccountId = latest.account?.id || data.account?.id || null;
    state.activeAccount = data.account || latest.account || null;
    if (state.activeAccountId) localStorage.setItem(ACTIVE_ACCOUNT_KEY, state.activeAccountId);
    state.transactions = (data.transactions || []).map(t => ({ ...t, date: new Date(t.date) }));
    state.investments = data.investments || [];
    state.alerts = data.alerts || [];
    state.stats = data.stats || {};

    buildDashboard();
    buildTransactionsTable();
    buildInvestmentSection();
    buildAlertsSection();
    buildBeneficiaries();
    renderHeaderAccountInfo(data.account || latest.account);
    renderFocusedAccountControl(data.account || latest.account);
    renderActiveContext();
    updateAlertBadges();
    await updateActiveAccountsMenu(state.activeAccountId);
    if (state.activeAccountId) _highlightActiveAccount(state.activeAccountId);
    setStatusBadge('ready', `${state.transactions.length} transacoes`);

    document.querySelectorAll('.nav-item:not(.account-nav-item)').forEach(n => n.classList.remove('active'));
    document.getElementById('nav-dashboard')?.classList.add('active');
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById('section-dashboard')?.classList.add('active');
  } catch (err) {
    console.error('Erro ao carregar dados iniciais:', err);
  }
}

// ── State ────────────────────────────────────────────────────
const state = {
  sessionId:    null,
  transactions: [],
  investments:  [],
  alerts:       [],
  stats:        null,
  accounts:     [],
  activeAccount: null,
  charts:       {},
  txPage:       1,
  txPageSize:   25,
  txFiltered:   [],
  sortCol:      'date',
  sortDir:      -1,
  resolveAlertId: null,
  activeAccountId: null
};

// ── Toast (#3 — com ação opcional) ───────────────────────────
function toast(msg, type='info', dur=3500, action=null) {
  const icons = { success:'✅', error:'❌', info:'ℹ️' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.style.display = 'flex'; el.style.alignItems = 'center'; el.style.gap = '8px';
  let html = `<span>${icons[type]||'ℹ️'}</span><span style="flex:1">${msg}</span>`;
  if (action && action.label && action.fn) {
    html += `<button class="toast-action" id="ta-${Date.now()}">${escHtml(action.label)}</button>`;
  }
  el.innerHTML = html;
  if (action && action.label && action.fn) {
    el.querySelector('.toast-action').addEventListener('click', () => { action.fn(); el.remove(); });
  }
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => { if (el.parentNode) el.style.animation='none'; }, dur-300);
  setTimeout(() => el.remove(), dur);
}

// ── Navigation ────────────────────────────────────────────────
function setNav(el) {
  // Mantém o destaque da conta ativa (.account-nav-item) intacto ao trocar de seção
  document.querySelectorAll('.nav-item:not(.account-nav-item)').forEach(n => n.classList.remove('active'));
  el.classList.add('active');
  const target = el.getAttribute('href').replace('#','');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById(target)?.classList.add('active');
  closeSidebar();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  // Lazy-load sections
  if (target === 'section-accounts')     loadAccounts();
  if (target === 'section-history')      loadHistory();
  if (target === 'section-beneficiaries') buildBeneficiaries();
  if (target === 'section-cross')         loadCrossAnalysis();
  if (target === 'section-compare')       loadCompareSessions();
  if (target === 'section-audit')         initAuditTrail();
}

// ── Upload ────────────────────────────────────────────────────
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
}

async function handleFiles(files) {
  if (!files.length) return;

  // #9 — Validação de tipos no frontend
  const ALLOWED_EXT = ['.ofx', '.txt', '.pdf', '.zip'];
  const invalid = [...files].filter(f => {
    const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase();
    return !ALLOWED_EXT.includes(ext);
  });
  if (invalid.length) {
    toast(`Arquivo(s) inválido(s): ${invalid.map(f => f.name).join(', ')} — Aceitos: OFX, TXT, PDF, ZIP`, 'error', 5000);
    return;
  }

  showLoader('Enviando arquivos…', 10);
  const form = new FormData();
  for (const f of files) form.append('files', f);
  try {
    const r    = await fetch(`${API}/upload`, { method: 'POST', body: form });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error);
    state.sessionId = data.sessionId;
    renderFileList(data.files);
    document.getElementById('btn-clear').style.display = 'inline-flex';
    setStatusBadge('loading', `${data.fileCount} arquivo(s) prontos`);
    toast(`${data.fileCount} arquivo(s) carregados`, 'success', 3500, { label: 'Analisar agora', fn: () => runAnalysis() });
    setProgress(100);
  } catch(err) { toast('Erro no upload: ' + err.message, 'error'); }
  finally { hideLoader(); }
}

function renderFileList(files) {
  const icons = { '.ofx':'🏦', '.txt':'📄', '.zip':'🗜️' };
  const cls   = { '.ofx':'type-ofx', '.txt':'type-txt', '.zip':'type-zip' };
  document.getElementById('file-list').innerHTML = files.map(f => `
    <div class="file-item">
      <span class="file-item-icon">${icons[f.ext]||'📁'}</span>
      <span class="file-item-name">${f.name}</span>
      <span class="file-item-size">${fmtBytes(f.size)}</span>
      <span class="file-item-type ${cls[f.ext]||''}">${(f.ext||'').replace('.','').toUpperCase()}</span>
    </div>`).join('');
  document.getElementById('file-list-container').style.display = 'block';
}

// ── Analyze ───────────────────────────────────────────────────
async function runAnalysis() {
  if (!state.sessionId) { toast('Faça o upload primeiro.','error'); return; }
  showLoader('Parsing OFX e TXT…', 20, 1, 3);
  try {
    setProgress(30);
    const body = state.activeAccountId ? { accountId: state.activeAccountId } : {};
    const r1 = await fetch(`${API}/analyze/${state.sessionId}`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
    const job = await r1.json();
    if (!r1.ok) throw new Error(job.error);

    let targetSessionId = state.sessionId;
    let mainAccount = null;

    if (job.accountsAnalyzed && job.accountsAnalyzed.length > 0) {
      const firstAcc = job.accountsAnalyzed[0];
      targetSessionId = firstAcc.sessionId;
      mainAccount = firstAcc.account;
      toast(`Detectadas ${job.accountsAnalyzed.length} contas diferentes! Exibindo a primeira.`, 'info');
    }

    setProgress(60); updateLoader('Carregando resultados…', 2, 3);
    const r2   = await fetch(`${API}/sessions/${targetSessionId}`);
    const data = await r2.json();
    if (!r2.ok) throw new Error(data.error);

    state.transactions = (data.transactions||[]).map(t=>({...t, date:new Date(t.date)}));
    state.investments  = data.investments||[];
    state.alerts       = data.alerts||[];
    state.stats        = data.stats||{};
    state.activeAccount = data.account || mainAccount || null;

    setProgress(80); updateLoader('Construindo dashboard…', 3, 3);
    await sleep(80);

    buildDashboard();
    buildTransactionsTable();
    buildInvestmentSection();
    buildAlertsSection();
    buildBeneficiaries();

    const finalAcc = data.account || mainAccount;
    await updateActiveAccountsMenu(finalAcc?.id || null);
    renderHeaderAccountInfo(finalAcc);
    if (finalAcc) _highlightActiveAccount(finalAcc.id);
    renderActiveContext();

    setProgress(100);
    setStatusBadge('ready', `${state.transactions.length} transações`);
    updateAlertBadges();

    const critCount = state.alerts.filter(a=>a.severity==='critical').length;
    const warnCount = state.alerts.filter(a=>a.severity==='warning').length;
    toast(`Análise concluída: ${critCount} crítico(s), ${warnCount} alerta(s)`, 'success', 4000,
      critCount > 0 ? { label: 'Ver alertas', fn: () => document.getElementById('nav-alerts')?.click() } : null);
    document.getElementById('nav-dashboard').click();
  } catch(err) {
    toast('Erro na análise: ' + err.message, 'error');
    setStatusBadge('error', 'Erro');
  } finally { hideLoader(); }
}

// Armazena todas as contas (para filtro/ordenação da sidebar e do seletor rápido)
let _allSidebarAccounts = [];
let _sidebarAccountSort = 'recent';

function setSidebarAccountSort(mode) {
  _sidebarAccountSort = mode;
  filterSidebarAccounts(document.getElementById('sidebar-account-search')?.value || '');
}

function _sortAccounts(accounts, mode) {
  const list = [...accounts];
  if (mode === 'name')        list.sort((a,b) => a.name.localeCompare(b.name, 'pt-BR'));
  else if (mode === 'number') list.sort((a,b) => a.number.localeCompare(b.number, 'pt-BR', {numeric:true}));
  else if (mode === 'bank')   list.sort((a,b) => (a.bank||'').localeCompare(b.bank||'', 'pt-BR') || a.name.localeCompare(b.name, 'pt-BR'));
  // 'recent' mantém a ordem vinda da API (created_at DESC)
  return list;
}

function filterSidebarAccounts(query) {
  const q = query.toLowerCase().trim();
  const menu = document.getElementById('dynamic-accounts-menu');
  if (!menu) return;
  const filtered = q
    ? _allSidebarAccounts.filter(a => a.name.toLowerCase().includes(q) || a.number.toLowerCase().includes(q) || (a.bank||'').toLowerCase().includes(q))
    : _allSidebarAccounts;
  _renderSidebarMenu(menu, _sortAccounts(filtered, _sidebarAccountSort), state.activeAccountId);
}

function _renderSidebarMenu(menu, accounts, activeAccountId) {
  if (!accounts.length) {
    menu.innerHTML = `<li style="padding: 6px 11px; font-size: 0.75rem; color: var(--text-3); font-style: italic;">Nenhuma conta encontrada</li>`;
    return;
  }
  menu.innerHTML = accounts.map(acc => {
    const activeClass = acc.id === activeAccountId ? 'active' : '';
    return `
      <li>
        <a href="#section-dashboard" class="nav-item account-nav-item ${activeClass}" data-account-id="${acc.id}" onclick="selectAccount('${acc.id}')" title="${escHtml(acc.name)} — ${escHtml(acc.bank||'')} • Conta ${escHtml(acc.number)}">
          <span class="account-nav-row">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
            <span class="account-nav-name">${escHtml(acc.name)}</span>
          </span>
          <span class="account-nav-meta">${escHtml(acc.bank||'')} • Cc. ${escHtml(acc.number)}</span>
        </a>
      </li>`;
  }).join('');
}

async function updateActiveAccountsMenu(activeAccountId) {
  const menu = document.getElementById('dynamic-accounts-menu');
  const countEl = document.getElementById('accounts-menu-count');
  if (!menu) return;
  if (activeAccountId !== undefined) state.activeAccountId = activeAccountId;
  try {
    const r = await fetch(`${API}/accounts`);
    const accounts = await r.json();
    _allSidebarAccounts = Array.isArray(accounts) ? accounts : [];
    renderFocusedAccountControl();
    if (countEl) countEl.textContent = _allSidebarAccounts.length ? `(${_allSidebarAccounts.length})` : '';
    if (!_allSidebarAccounts.length) {
      menu.innerHTML = `<li style="padding: 6px 11px; font-size: 0.75rem; color: var(--text-3); font-style: italic;">Nenhuma conta cadastrada</li>`;
      return;
    }
    _renderSidebarMenu(menu, _sortAccounts(_allSidebarAccounts, _sidebarAccountSort), state.activeAccountId);
  } catch (err) {
    console.error('Erro ao construir menu de contas:', err);
  }
}

function renderFocusedAccountControl(account) {
  const selects = [
    document.getElementById('account-focus-select'),
    document.getElementById('dashboard-account-select')
  ].filter(Boolean);
  const summary = document.getElementById('account-focus-summary');
  const dashSummary = document.getElementById('dashboard-account-summary');
  if (!selects.length) return;

  const selectedId = account?.id || state.activeAccountId || localStorage.getItem(ACTIVE_ACCOUNT_KEY) || '';
  const selectedAccount = account || _allSidebarAccounts.find(a => a.id === selectedId) || null;

  const options = '<option value="">Escolha uma conta...</option>' +
    _allSidebarAccounts.map(acc => `<option value="${escHtml(acc.id)}">${escHtml(acc.name)} - Conta ${escHtml(acc.number)}</option>`).join('');
  selects.forEach(select => {
    select.innerHTML = options;
    select.value = selectedId;
  });

  if (selectedAccount) {
    const text = `${selectedAccount.name} | ${selectedAccount.bank || 'Banco'} | Conta ${selectedAccount.number}`;
    if (summary) summary.textContent = text;
    if (dashSummary) dashSummary.textContent = text;
  } else {
    if (summary) summary.textContent = 'Selecione uma conta para ver somente os dados dela.';
    if (dashSummary) dashSummary.textContent = 'Selecione uma conta para ver o dashboard dela.';
  }
}

function handleAccountFocusChange(accountId, openNow = false) {
  if (!accountId) {
    clearFocusedAccount();
    return;
  }
  localStorage.setItem(ACTIVE_ACCOUNT_KEY, accountId);
  state.activeAccountId = accountId;
  const account = _allSidebarAccounts.find(a => a.id === accountId);
  renderFocusedAccountControl(account);
  if (openNow) selectAccount(accountId);
}

async function openFocusedAccount(selectId = 'account-focus-select') {
  const accountId = document.getElementById(selectId)?.value || state.activeAccountId;
  if (!accountId) { toast('Selecione uma conta primeiro.', 'error'); return; }
  await selectAccount(accountId);
}

function clearFocusedAccount() {
  localStorage.removeItem(ACTIVE_ACCOUNT_KEY);
  clearAll();
  renderFocusedAccountControl(null);
  toast('Seleção de conta limpa.', 'info');
}

// ── Account quick-switcher (header) ──────────────────────────
function toggleAccountSwitcher(e) {
  e.stopPropagation();
  const popover = document.getElementById('account-switcher-popover');
  const trigger = document.getElementById('account-switcher-trigger');
  if (popover.classList.contains('open')) { closeAccountSwitcher(); return; }
  if (!_allSidebarAccounts.length) { toast('Nenhuma conta cadastrada ainda. Carregue um extrato ou cadastre uma conta.', 'info'); return; }
  popover.classList.add('open');
  trigger.classList.add('open');
  const search = document.getElementById('switcher-search-input');
  search.value = '';
  renderSwitcherList(_allSidebarAccounts);
  setTimeout(() => search.focus(), 30);
}

function closeAccountSwitcher() {
  document.getElementById('account-switcher-popover')?.classList.remove('open');
  document.getElementById('account-switcher-trigger')?.classList.remove('open');
}

document.addEventListener('click', (e) => {
  const popover = document.getElementById('account-switcher-popover');
  const trigger = document.getElementById('account-switcher-trigger');
  if (popover?.classList.contains('open') && !popover.contains(e.target) && !trigger?.contains(e.target)) {
    closeAccountSwitcher();
  }
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeAccountSwitcher(); closeSidebar(); } });

function filterSwitcherList(query) {
  const q = query.toLowerCase().trim();
  const filtered = q
    ? _allSidebarAccounts.filter(a => a.name.toLowerCase().includes(q) || a.number.toLowerCase().includes(q) || (a.bank||'').toLowerCase().includes(q))
    : _allSidebarAccounts;
  renderSwitcherList(filtered);
}

function renderSwitcherList(accounts) {
  const list = document.getElementById('account-switcher-list');
  if (!accounts.length) { list.innerHTML = `<p class="switcher-empty">Nenhuma conta encontrada para esta busca.</p>`; return; }
  list.innerHTML = accounts.map(acc => `
    <div class="switcher-item ${acc.id === state.activeAccountId ? 'active' : ''}" data-account-id="${acc.id}" onclick="selectAccount('${acc.id}')">
      <span class="switcher-item-name">🏦 ${escHtml(acc.name)}</span>
      <span class="switcher-item-meta">${escHtml(acc.bank||'')} • Agência ${escHtml(acc.agency||'?')} • Conta ${escHtml(acc.number)}</span>
    </div>`).join('');
}

function renderHeaderAccountInfo(account) {
  const el = document.getElementById('header-account-info');
  if (!el) return;
  if (!account) { el.innerHTML = '<span class="account-switcher-placeholder">Nenhuma conta carregada</span>'; return; }
  el.innerHTML = `<span>🏦</span> <span><strong>${escHtml(account.name)}</strong> — Agência ${escHtml(account.agency||'?')} | Conta ${escHtml(account.number)}</span>`;
}

function renderActiveContext() {
  const account = state.activeAccount;
  const stats = state.stats || {};
  const periods = stats.periods || [];
  const periodLabel = periods.length ? `${periods[0]} -> ${periods[periods.length - 1]}` : '?';
  const unresolved = state.alerts.filter(a => !a.resolved).length;

  const dashboard = document.getElementById('active-context-grid');
  if (dashboard) {
    if (!account || !state.sessionId) {
      dashboard.style.display = 'none';
      dashboard.innerHTML = '';
    } else {
      dashboard.style.display = 'grid';
      dashboard.innerHTML = [
        ['Conta ativa', `${escHtml(account.name)}<span>${escHtml(account.number || '')}</span>`],
        ['Periodo', `${escHtml(periodLabel)}<span>${state.transactions.length} transacoes</span>`],
        ['Alertas pendentes', `${unresolved}<span>${state.alerts.length} total</span>`],
        ['Sessao', `${escHtml(String(state.sessionId).slice(0, 8))}<span>contexto atual</span>`]
      ].map(([label, value]) => `<div class="context-card"><span>${label}</span><strong>${value}</strong></div>`).join('');
    }
  }

  const exportBox = document.getElementById('export-context');
  if (exportBox) {
    if (!account || !state.sessionId) {
      exportBox.innerHTML = '<p class="empty-state">Nenhuma conta carregada para exportacao.</p>';
    } else {
      exportBox.innerHTML = `
        <div class="context-card context-card-wide">
          <span>Relatorio atual</span>
          <strong>${escHtml(account.name)} - Conta ${escHtml(account.number || '')}</strong>
          <small>Periodo: ${escHtml(periodLabel)} | ${state.transactions.length} transacoes | ${unresolved} alerta(s) pendente(s)</small>
        </div>`;
    }
  }
}

// Marca a conta ativa nos dois seletores (sidebar + popover do header)
function _highlightActiveAccount(accountId) {
  document.querySelectorAll('.account-nav-item, .switcher-item').forEach(n => n.classList.remove('active'));
  document.querySelectorAll(`[data-account-id="${accountId}"]`).forEach(n => n.classList.add('active'));
}

async function selectAccount(accountId) {
  closeAccountSwitcher();
  closeSidebar();
  _highlightActiveAccount(accountId);
  localStorage.setItem(ACTIVE_ACCOUNT_KEY, accountId);

  showLoader('Buscando histórico da conta…', 20);
  try {
    const r = await fetch(`${API}/accounts/${accountId}/history`);
    const data = await r.json();

    if (!data.history || !data.history.length) {
      toast('Nenhuma sessão de análise anterior encontrada para esta conta.', 'info');
      clearAll();
      hideLoader();
      return;
    }

    // Load the latest session from this account
    const latestSession = data.history[0];
    state.sessionId = latestSession.id;
    state.activeAccountId = accountId;

    setProgress(60); updateLoader('Carregando resultados…');
    const r2   = await fetch(`${API}/sessions/${latestSession.id}`);
    const resData = await r2.json();
    if (!r2.ok) throw new Error(resData.error);

    state.transactions = (resData.transactions||[]).map(t=>({...t, date:new Date(t.date)}));
    state.investments  = resData.investments||[];
    state.alerts       = resData.alerts||[];
    state.stats        = resData.stats||{};
    state.activeAccount = resData.account || data.account || null;

    buildDashboard();
    buildTransactionsTable();
    buildInvestmentSection();
    buildAlertsSection();
    buildBeneficiaries();

    renderHeaderAccountInfo(data.account);
    renderFocusedAccountControl(data.account);
    renderActiveContext();
    _highlightActiveAccount(accountId);

    setProgress(100);
    setStatusBadge('ready', `${state.transactions.length} transações`);

    updateAlertBadges();

    toast(`Dados da conta ${data.account.number} carregados com sucesso!`, 'success');

    // Jump to dashboard (preserva o destaque da conta selecionada)
    document.querySelectorAll('.nav-item:not(.account-nav-item)').forEach(n => n.classList.remove('active'));
    document.getElementById('nav-dashboard').classList.add('active');
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById('section-dashboard').classList.add('active');
  } catch (err) {
    toast('Erro ao carregar conta: ' + err.message, 'error');
  } finally {
    hideLoader();
  }
}

// ── Mobile sidebar toggle ─────────────────────────────────────
function toggleSidebar() {
  document.getElementById('sidebar')?.classList.toggle('open');
  document.getElementById('sidebar-overlay')?.classList.toggle('open');
}
function closeSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.getElementById('sidebar-overlay')?.classList.remove('open');
}

function clearAll() {
  localStorage.removeItem(ACTIVE_ACCOUNT_KEY);
  Object.assign(state, { sessionId:null, transactions:[], investments:[], alerts:[], stats:null, txPage:1, txFiltered:[], activeAccountId:null, activeAccount:null });
  Object.values(state.charts).forEach(c=>c?.destroy?.());
  state.charts = {};
  document.getElementById('file-list').innerHTML = '';
  document.getElementById('file-list-container').style.display = 'none';
  document.getElementById('btn-clear').style.display = 'none';
  document.getElementById('file-input').value = '';
  document.getElementById('alerts-badge').style.display = 'none';
  document.getElementById('kpi-grid').innerHTML = '';
  document.getElementById('transactions-table-container').innerHTML = '<p class="empty-state">Nenhuma transação.</p>';
  document.getElementById('tx-pagination').innerHTML = '';
  document.getElementById('alerts-container').innerHTML = '<p class="empty-state">Nenhuma análise carregada.</p>';
  document.getElementById('investment-container').innerHTML = '<p class="empty-state">Carregue extratos TXT.</p>';
  document.getElementById('beneficiaries-container').innerHTML = '<p class="empty-state">Execute uma análise primeiro.</p>';
  document.getElementById('tx-summary-grid').style.display = 'none';
  renderHeaderAccountInfo(null);
  _highlightActiveAccount(null);
  renderFocusedAccountControl(null);
  renderActiveContext();
  setStatusBadge('idle', 'Aguardando');
  toast('Sessão limpa', 'info');
}

// ── Dashboard (#1 — KPIs com drill-down) ─────────────────────
function buildDashboard() {
  const s = state.stats;
  if (!s) {
    document.getElementById('kpi-grid').innerHTML = '<p class="empty-state">Selecione uma conta para carregar o dashboard.</p>';
    renderActiveContext();
    return;
  }

  // #5 — Skeleton antes de renderizar
  document.getElementById('kpi-grid').innerHTML = `
    <div class="skeleton-kpi-grid" style="grid-column:1/-1">
      ${Array(6).fill('<div class="skeleton skeleton-kpi"></div>').join('')}
    </div>`;

  // Pequeno delay para o skeleton aparecer e depois renderizar
  requestAnimationFrame(() => {
    const kpis = [
      { label:'Transações',       value: s.totalTransactions, sub:`${s.periods?.length||0} meses`, color:'var(--primary)',  drill: () => drillKpi('transactions') },
      { label:'Entradas C-C',     value:`R$ ${fmtM(s.totalCredits)}`, sub:'Total creditado', color:'var(--green)',  drill: () => drillKpi('credits') },
      { label:'Saídas C-C',       value:`R$ ${fmtM(s.totalDebits)}`, sub:'Total debitado', color:'var(--red)',    drill: () => drillKpi('debits') },
      { label:'Saldo Aplicação',  value:`R$ ${fmtM(s.lastBalance)}`, sub:s.lastPeriod||'-', color:'var(--cyan)',   drill: null },
      { label:'Rendimento Total', value:`R$ ${fmtM(s.totalRendimento)}`, sub:'Bruto acumulado', color:'var(--green)', drill: null },
      { label:'Alertas',          value:`${s.criticalAlerts}🔴 ${s.warningAlerts}🟡`, sub:`${s.totalAlerts} divergências`, color:'var(--yellow)', drill: () => drillKpi('alerts') }
    ];
    document.getElementById('kpi-grid').innerHTML = kpis.map((k, i) => `
      <div class="kpi-card" style="--kpi-color:${k.color};${k.drill ? 'cursor:pointer;' : ''}" 
           id="kpi-card-${i}" title="${k.drill ? 'Clique para detalhar' : ''}" 
           onclick="${k.drill ? `_kpiDrills[${i}]()` : ''}">
        <span class="kpi-label">${k.label}</span>
        <span class="kpi-value">${k.value}</span>
        <span class="kpi-sub">${k.sub}</span>
      </div>`).join('');

    // Store drill functions
    window._kpiDrills = kpis.map(k => k.drill || (() => {}));

    buildCharts();
    buildRiskScoreBar();
    buildDailyBalanceChart();
    buildWeekdayHeatmap();
  });
}

// #1 — KPI Drill-down
function drillKpi(type) {
  if (type === 'alerts') {
    document.querySelectorAll('.nav-item:not(.account-nav-item)').forEach(n => n.classList.remove('active'));
    document.getElementById('nav-alerts')?.classList.add('active');
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById('section-alerts')?.classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }
  // Transactions with auto-filter
  document.querySelectorAll('.nav-item:not(.account-nav-item)').forEach(n => n.classList.remove('active'));
  document.getElementById('nav-transactions')?.classList.add('active');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById('section-transactions')?.classList.add('active');
  const dirSel = document.getElementById('tx-direction-filter');
  if (dirSel) {
    dirSel.value = type === 'credits' ? 'credit' : type === 'debits' ? 'debit' : '';
    filterTransactions();
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
  toast(`Exibindo ${type === 'credits' ? 'entradas' : type === 'debits' ? 'saídas' : 'todas as transações'}`, 'info', 2000);
}

async function buildCharts() {
  Object.values(state.charts).forEach(c=>c?.destroy?.());
  state.charts={};

  // Helper: revela canvas e oculta empty state
  function showChart(id) {
    const canvas = document.getElementById(id);
    const empty  = document.getElementById(id + '-empty');
    if (canvas) canvas.style.display = '';
    if (empty)  empty.style.display  = 'none';
  }

  const inv = (state.stats?.monthlyInvestments||[]).sort((a,b)=>a.periodSort.localeCompare(b.periodSort));
  const flow = state.stats?.monthlyFlow||{};
  const flowKeys = Object.keys(flow).sort();

  // Chart 1: Balance vs Rendimento
  if (inv.length) {
    showChart('chart-balance');
    state.charts.balance = new Chart(document.getElementById('chart-balance').getContext('2d'), {
      type:'line',
      data:{ labels:inv.map(i=>i.period),
        datasets:[
          { label:'Saldo Aplicação', data:inv.map(i=>i.saldoAtual), borderColor:'#6366f1', backgroundColor:'rgba(99,102,241,.1)', borderWidth:2.5, pointRadius:5, tension:.35, fill:true },
          { label:'Rendimento Mês', data:inv.map(i=>i.rendBruto), borderColor:'#10b981', backgroundColor:'rgba(16,185,129,.08)', borderWidth:2, pointRadius:4, tension:.35, fill:true, yAxisID:'y2' }
        ]},
      options:lineOpts('Saldo (R$)','Rendimento (R$)')
    });
  }

  // Chart 2: Cash Flow
  if (flowKeys.length) {
    showChart('chart-flow');
    state.charts.flow = new Chart(document.getElementById('chart-flow').getContext('2d'), {
      type:'bar',
      data:{ labels:flowKeys,
        datasets:[
          { label:'Entradas', data:flowKeys.map(k=>flow[k].in),  backgroundColor:'rgba(16,185,129,.7)', borderRadius:5 },
          { label:'Saídas',   data:flowKeys.map(k=>flow[k].out), backgroundColor:'rgba(239,68,68,.65)',  borderRadius:5 }
        ]},
      options:barOpts()
    });
  }

  // Chart 3: Rentabilidade vs CDI
  try {
    const cdiData = await fetch(`${API}/cdi`).then(r=>r.json());
    if (Array.isArray(cdiData) && cdiData.length && inv.length) {
      showChart('chart-cdi');
      const cdiMap = {};
      for (const d of cdiData) { const [dd,mm,yyyy]=d.date.split('/'); cdiMap[`${mm}/${yyyy}`]=d.value; }
      state.charts.cdi = new Chart(document.getElementById('chart-cdi').getContext('2d'), {
        type:'line',
        data:{ labels:inv.map(i=>i.period),
          datasets:[
            { label:'Rentabilidade Mês %', data:inv.map(i=>i.rentMonth), borderColor:'#6366f1', borderWidth:2.5, pointRadius:4, tension:.3 },
            { label:'CDI Mensal %', data:inv.map(i=>{
              if (!i.periodSort) return null;
              const [yr, mon] = i.periodSort.split('-');
              const k = `${mon}/${yr}`;
              return cdiMap[k] || null;
            }), borderColor:'#f59e0b', borderDash:[5,3], borderWidth:2, pointRadius:3, tension:.3 }
          ]},
        options: { ...lineOpts('% Mês',''), plugins:{ legend:{ labels:{ color:'#94a3b8', font:{size:11} } } } }
      });
    }
  } catch {}

  // Chart 4: Pie - Saída por categoria
  const top = state.stats?.topBeneficiaries||[];
  if (top.length) {
    showChart('chart-pie');
    const colors = ['#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#f97316','#ef4444','#ec4899','#14b8a6','#84cc16'];
    state.charts.pie = new Chart(document.getElementById('chart-pie').getContext('2d'), {
      type:'doughnut',
      data:{ labels:top.map(b=>b.name.substring(0,25)),
        datasets:[{ data:top.map(b=>b.total), backgroundColor:colors.slice(0,top.length), borderColor:'transparent', borderWidth:4 }] },
      options:{ responsive:true, plugins:{ legend:{ position:'right', labels:{ color:'#94a3b8', font:{size:10}, boxWidth:12 } } }, cutout:'68%' }
    });
  }
}

// ── Transactions Table ────────────────────────────────────────
function buildTransactionsTable() {
  const months = [...new Set(state.transactions.map(t=>t.dateStr?.substring(3)).filter(Boolean))].sort();
  const sel = document.getElementById('tx-month-filter');
  sel.innerHTML = '<option value="">Todos os meses</option>' +
    months.map(m=>`<option value="${m}">${m}</option>`).join('');
  state.txPage = 1;
  filterTransactions();
}

// filterTransactions: definição única na seção "Advanced Transaction Filters" (#9)

function sortBy(col) {
  if (state.sortCol === col) state.sortDir *= -1;
  else { state.sortCol = col; state.sortDir = -1; }
  renderPage();
}

function renderPage() {
  const sorted = [...state.txFiltered].sort((a,b) => {
    let va = a[state.sortCol], vb = b[state.sortCol];
    if (state.sortCol === 'date') { va = new Date(va); vb = new Date(vb); }
    if (state.sortCol === 'amount') { va = Math.abs(va); vb = Math.abs(vb); }
    return (va > vb ? 1 : va < vb ? -1 : 0) * state.sortDir;
  });
  const total = sorted.length;
  renderTxSummary(sorted);
  const pages = Math.ceil(total / state.txPageSize);
  const start = (state.txPage - 1) * state.txPageSize;
  const page  = sorted.slice(start, start + state.txPageSize);

  const typeChip = t => {
    if (t==='DEP')   return '<span class="type-chip chip-dep">DEP</span>';
    if (t==='DEBIT') return '<span class="type-chip chip-debit">DÉBITO</span>';
    return '<span class="type-chip chip-xfer">XFER</span>';
  };

  const container = document.getElementById('transactions-table-container');
  if (!page.length) { container.innerHTML = '<p class="empty-state">Nenhuma transação.</p>'; return; }
  container.innerHTML = `
    <div class="data-table-wrap">
      <table class="data-table">
        <thead><tr>
          <th onclick="sortBy('dateStr')">Data ↕</th>
          <th onclick="sortBy('type')">Tipo ↕</th>
          <th onclick="sortBy('amount')">Valor ↕</th>
          <th>Descrição</th>
          <th onclick="sortBy('period')">Período ↕</th>
          <th>Status</th>
        </tr></thead>
        <tbody>
          ${page.map(t=>`
            <tr class="${t.flagged?'flagged':''}" title="${escHtml((t.flags||[]).join(', '))}">
              <td>${t.dateStr}</td>
              <td>${typeChip(t.type)}</td>
              <td class="${t.amount>=0?'amount-pos':'amount-neg'}">
                ${t.amount>=0?'+':''}R$ ${Math.abs(t.amount).toFixed(2).replace('.',',')}
              </td>
              <td>${escHtml((t.memo||'').substring(0,70))}${t.flagged?'<span class="flag-icon">⚠️</span>':''}</td>
              <td style="color:var(--text-3);font-size:.73rem">${t.period||''}</td>
              <td>${(t.flags||[]).map(f=>`<span class="account-tag" style="font-size:.62rem">${f}</span>`).join(' ')}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>
    <p style="margin-top:.5rem;font-size:.75rem;color:var(--text-3)">${total} transação(ões) — página ${state.txPage} de ${pages}</p>`;

  // Pagination
  const pag = document.getElementById('tx-pagination');
  if (pages <= 1) { pag.innerHTML=''; return; }
  let btns = '';
  for (let i=1;i<=pages;i++) btns += `<button class="page-btn ${i===state.txPage?'active':''}" onclick="goPage(${i})">${i}</button>`;
  pag.innerHTML = btns;
}

function renderTxSummary(rows) {
  const el = document.getElementById('tx-summary-grid');
  if (!el) return;
  if (!state.transactions.length) {
    el.style.display = 'none';
    return;
  }
  const credits = rows.filter(t => t.amount > 0).reduce((s, t) => s + t.amount, 0);
  const debits = rows.filter(t => t.amount < 0).reduce((s, t) => s + Math.abs(t.amount), 0);
  const balance = credits - debits;
  const flagged = rows.filter(t => t.flagged).length;
  el.style.display = 'grid';
  el.innerHTML = [
    ['Transacoes filtradas', `${rows.length}<span>de ${state.transactions.length}</span>`],
    ['Entradas filtradas', `R$ ${fmtM(credits)}<span>creditos</span>`],
    ['Saidas filtradas', `R$ ${fmtM(debits)}<span>debitos</span>`],
    ['Saldo do filtro', `R$ ${fmtM(balance)}<span>${flagged} sinalizada(s)</span>`]
  ].map(([label, value]) => `<div class="context-card"><span>${label}</span><strong>${value}</strong></div>`).join('');
}

function goPage(p) { state.txPage = p; renderPage(); window.scrollTo({ top:300, behavior:'smooth' }); }

// ── Investment ────────────────────────────────────────────────
function buildInvestmentSection() {
  const c = document.getElementById('investment-container');
  const sorted = [...state.investments].sort((a,b)=>(a.periodSort||'').localeCompare(b.periodSort||''));
  if (!sorted.length) { c.innerHTML='<p class="empty-state">Nenhum extrato TXT carregado.</p>'; buildFundEvolutionChart(); return; }
  c.innerHTML = sorted.map(inv => {
    const s=inv.summary||{}, r=inv.rentability||{};
    const rows=[
      ['Saldo Anterior', s.saldoAnterior||0, ''],
      ['Aplicações (+)', s.aplicacoes||0, 'pos'],
      ['Resgates (−)',   s.resgates||0, 'neg'],
      ['Rend. Bruto',   s.rendBruto||0, 'pos'],
      ['IR',            s.ir||0, ''],
      ['Saldo Atual',   s.saldoAtual||0, 'cyan'],
      ['Rent. Mês %',   `${(r.month||0).toFixed(4)}%`, 'pos'],
      ['Rent. Ano %',   `${(r.year||0).toFixed(4)}%`, 'pos'],
      ['Rent. 12m %',   `${(r.y12||0).toFixed(4)}%`, 'pos']
    ];
    return `<div class="invest-card">
      <div class="invest-card-header">
        <span class="invest-card-title">${inv.period||'?'}</span>
        <span class="invest-card-period">${inv.account||''}</span>
      </div>
      <div class="invest-summary">
        ${rows.map(([lbl,val,cls])=>`
          <div class="invest-sum-item">
            <span class="invest-sum-label">${lbl}</span>
            <span class="invest-sum-value ${cls==='cyan'?'':cls}" style="${cls==='cyan'?'color:var(--cyan)':''}">
              ${typeof val==='number'?'R$ '+fmtM(val):val}
            </span>
          </div>`).join('')}
      </div>
    </div>`;
  }).join('');
  buildFundEvolutionChart();
}

// ── Alerts ────────────────────────────────────────────────────
let alertFilterValue = '';
function filterAlerts() {
  alertFilterValue = document.getElementById('alert-filter').value;
  buildAlertsSection();
}

function buildAlertsSection() {
  const c = document.getElementById('alerts-container');
  let alerts = state.alerts;
  if (alertFilterValue === 'critical')    alerts = alerts.filter(a=>a.severity==='critical');
  else if (alertFilterValue === 'warning') alerts = alerts.filter(a=>a.severity==='warning');
  else if (alertFilterValue === 'info')    alerts = alerts.filter(a=>a.severity==='info');
  else if (alertFilterValue === 'resolved')   alerts = alerts.filter(a=>a.resolved);
  else if (alertFilterValue === 'unresolved') alerts = alerts.filter(a=>!a.resolved);

  if (!state.alerts.length) {
    c.innerHTML=`<div style="text-align:center;padding:3rem">
      <div style="font-size:3rem;margin-bottom:1rem">✅</div>
      <p style="color:var(--green);font-size:1rem;font-weight:600">Nenhuma divergência detectada</p>
      <p style="color:var(--text-3);font-size:.85rem;margin-top:.5rem">Todas as transações estão dentro dos padrões esperados.</p>
    </div>`; return;
  }

  const bySev = { critical:[], warning:[], info:[] };
  for (const a of alerts) (bySev[a.severity]||bySev.info).push(a);

  let html = `<div style="display:flex;gap:.625rem;flex-wrap:wrap;margin-bottom:1.5rem">`;
  const tot = state.alerts;
  if (tot.filter(a=>a.severity==='critical').length) html += `<span class="alert-count-badge badge-red">🔴 ${tot.filter(a=>a.severity==='critical').length} Crítico(s)</span>`;
  if (tot.filter(a=>a.severity==='warning').length)  html += `<span class="alert-count-badge badge-yellow">🟡 ${tot.filter(a=>a.severity==='warning').length} Atenção</span>`;
  if (tot.filter(a=>a.severity==='info').length)     html += `<span class="alert-count-badge badge-cyan">🔵 ${tot.filter(a=>a.severity==='info').length} Informativo(s)</span>`;
  html += `</div>`;

  for (const [sev, icon, label] of [['critical','🔴','Alertas Críticos'],['warning','🟡','Alertas de Atenção'],['info','🔵','Informativos']]) {
    if (!bySev[sev]?.length) continue;
    html += `<div class="alert-group"><p class="alert-group-title">${icon} ${label} (${bySev[sev].length})</p>`;
    html += bySev[sev].map(a=>`
      <div class="alert-item alert-${a.severity} ${a.resolved?'resolved':''}" id="alert-card-${a.id}">
        <span class="alert-icon">${a.icon||'⚠️'}</span>
        <div class="alert-body">
          <p class="alert-title">${escHtml(a.title)}</p>
          <p class="alert-desc">${escHtml(a.description)}</p>
          <div class="alert-meta">
            ${(a.evidence||[]).map(e=>`<span><strong>${e.label}:</strong> ${escHtml(e.value)}</span>`).join('')}
          </div>
          ${a.resolved ? `
            <div class="alert-resolved-badge" id="note-display-${a.id}">
              ✓ Resolvido${a.resolution_note ? ` — <em>${a.resolution_note.substring(0,80)}</em>` : ''}
              <button class="btn-ghost btn-sm" style="padding:1px 8px;margin-left:6px;font-size:.68rem" onclick="openNoteEditor('${a.id}', '${escHtml((a.resolution_note||'').replace(/'/g,"\\'"))}')">✏️ Editar nota</button>
            </div>` : ''}
          <div class="alert-actions">
            ${a.resolved
              ? `<button class="btn-ghost btn-sm" onclick="unresolveAlert('${a.id}')">↩ Reabrir Alerta</button>`
              : `<button class="btn-primary btn-sm" style="box-shadow:none;" onclick="openResolveModal('${a.id}', '${escHtml(a.title.replace(/'/g, "\\'"))}')">✓ Marcar como Resolvido</button>`
            }
          </div>
        </div>
      </div>`).join('');
    html += `</div>`;
  }
  c.innerHTML = html;
  injectAttachButtons();
}

// ── Beneficiaries ─────────────────────────────────────────────
function buildBeneficiaries() {
  const c = document.getElementById('beneficiaries-container');
  const top = state.stats?.topBeneficiaries||[];
  if (!top.length) { c.innerHTML='<p class="empty-state">Execute uma análise primeiro.</p>'; return; }
  const max = top[0]?.total||1;
  c.innerHTML = `<div class="bene-bar-wrap">
    ${top.map((b,i)=>`
      <div class="bene-bar-item">
        <div class="bene-bar-header">
          <span class="bene-bar-name">${i+1}. ${escHtml(b.name)}</span>
          <span class="bene-bar-amt">R$ ${fmtM(b.total)}</span>
        </div>
        <div class="bene-bar-track"><div class="bene-bar-fill" style="width:${(b.total/max*100).toFixed(1)}%"></div></div>
        <span class="bene-count">${b.count} transação(ões)</span>
      </div>`).join('')}
  </div>`;
}

// ── Accounts ──────────────────────────────────────────────────
async function loadAccounts() {
  try {
    const r = await fetch(`${API}/accounts`);
    const data = await r.json();
    state.accounts = Array.isArray(data) ? data : [];
    renderAccounts();
  } catch { document.getElementById('accounts-container').innerHTML = '<p class="empty-state">Erro ao carregar contas.</p>'; }
}

function renderAccounts() {
  const c = document.getElementById('accounts-container');
  const countEl = document.getElementById('accounts-total-count');
  if (countEl) countEl.textContent = state.accounts.length ? `(${state.accounts.length})` : '';
  if (!state.accounts.length) { c.innerHTML='<p class="empty-state">Nenhuma conta cadastrada. Clique em "+ Nova Conta".</p>'; return; }

  const query = (document.getElementById('accounts-search')?.value || '').toLowerCase().trim();
  const sortMode = document.getElementById('accounts-sort')?.value || 'recent';

  let list = query
    ? state.accounts.filter(a =>
        a.name.toLowerCase().includes(query) ||
        a.number.toLowerCase().includes(query) ||
        (a.agency||'').toLowerCase().includes(query) ||
        (a.bank||'').toLowerCase().includes(query))
    : [...state.accounts];

  if (sortMode === 'name')        list.sort((a,b) => a.name.localeCompare(b.name, 'pt-BR'));
  else if (sortMode === 'number') list.sort((a,b) => a.number.localeCompare(b.number, 'pt-BR', {numeric:true}));
  else if (sortMode === 'bank')   list.sort((a,b) => (a.bank||'').localeCompare(b.bank||'', 'pt-BR') || a.name.localeCompare(b.name, 'pt-BR'));
  // 'recent' preserva a ordem da API (created_at DESC)

  if (!list.length) { c.innerHTML = `<p class="empty-state">Nenhuma conta encontrada para "${escHtml(query)}".</p>`; return; }

  c.innerHTML = `<p style="font-size:.78rem;color:var(--text-3);margin-bottom:.875rem">Exibindo ${list.length} de ${state.accounts.length} conta(s)</p>
  <div class="account-grid">${list.map(a=>`
    <div class="account-card ${a.id === state.activeAccountId ? 'account-card-active' : ''}">
      <p class="account-card-title">🏦 ${escHtml(a.name)} ${a.id === state.activeAccountId ? '<span class="account-tag account-tag-active">Ativa</span>' : ''}</p>
      <p class="account-card-sub">${escHtml(a.bank)}</p>
      <div class="account-card-meta">
        <span class="account-tag">Ag. ${escHtml(a.agency||'?')}</span>
        <span class="account-tag">Cc. ${escHtml(a.number)}</span>
      </div>
      ${a.notes?`<p style="font-size:.76rem;color:var(--text-3);margin-top:.25rem">${escHtml(a.notes)}</p>`:''}
      <div class="account-card-actions">
        <button class="btn-ghost btn-sm" onclick="selectAccount('${a.id}')">📂 Abrir conta</button>
        <button class="btn-ghost btn-sm" onclick="openConfigModal('${a.id}', '${escHtml(a.name.replace(/'/g, "\\'"))}')">⚙️ Detectores</button>
        <button class="btn-ghost btn-sm" onclick="deleteAccount('${a.id}')">🗑️ Remover</button>
      </div>
    </div>`).join('')}</div>`;
}

function openAccountModal()  { document.getElementById('account-modal').style.display='flex'; }
function closeAccountModal() { document.getElementById('account-modal').style.display='none'; }

// ── Detector Config per Account (⚙️) ─────────────────────────
let _configAccountId = null;

// Descrições pt-BR das chaves numéricas de CONFIG, agrupadas por detector
const CONFIG_GROUPS = [
  ['Duplicatas', {
    MEMO_SIM_DUPLICATE: 'Similaridade mínima de memo (0–1) para considerar duplicata',
  }],
  ['Movimentação Atípica', {
    ATYPICAL_ZSCORE:     'Z-score base para débito atípico',
    ATYPICAL_MIN_VALUE:  'Valor mínimo (R$) avaliado',
    ATYPICAL_MIN_SAMPLE: 'Amostra mínima por categoria',
  }],
  ['Devoluções e Aplicações', {
    RETURN_WINDOW_DAYS:        'Janela (dias) para re-envio após devolução',
    MAX_UNAPPLIED_WINDOW_DAYS: 'Janela (dias) para aplicar recurso de OB',
    CASH_REMNANT_SURPLUS:      'Sobra ociosa mínima (R$) para alertar',
  }],
  ['Valores Redondos', {
    ROUND_AMOUNT_MIN:  'Valor mínimo (R$) para alertar redondo',
    ROUND_AMOUNT_STEP: 'Múltiplo considerado redondo (R$)',
  }],
  ['Horário e Calendário', {
    AFTER_HOURS_MIN_VALUE:  'Valor mínimo (R$) de PIX fora do horário',
    AFTER_HOURS_START_HOUR: 'Início do expediente (hora)',
    AFTER_HOURS_END_HOUR:   'Fim do expediente (hora)',
    WEEKEND_MIN_VALUE:      'Valor mínimo (R$) em fim de semana/feriado',
  }],
  ['FNAS', {
    FNAS_DIVERGENCE_PCT: 'Piso do limiar de divergência (0–1)',
  }],
  ['Fracionamento (Smurfing)', {
    SMURFING_MIN_ITEMS:      'Mínimo de pagamentos na janela',
    SMURFING_WINDOW_DAYS:    'Janela (dias)',
    SMURFING_MIN_TOTAL:      'Total mínimo (R$) na janela',
    SMURFING_CV_THRESHOLD:   'Coef. de variação máximo (valores idênticos)',
    SMURFING_VELOCITY_COUNT: 'Pagamentos para alerta de velocidade',
    SMURFING_VELOCITY_DAYS:  'Dias para alerta de velocidade',
  }],
  ['Lei de Benford', {
    BENFORD_MIN_SAMPLE:   'Amostra mínima de débitos',
    BENFORD_CHI2_WARNING: 'χ² para severidade atenção',
    BENFORD_CHI2_INFO:    'χ² para severidade informativa',
  }],
  ['Limite Licitatório', {
    PROCUREMENT_SKIRT_PCT: 'Faixa abaixo do limite (0–1) considerada suspeita',
  }],
  ['Aumento Gradual de Preços', {
    CREEP_MIN_MONTHS: 'Meses mínimos com pagamento ao fornecedor',
    CREEP_GROWTH_PCT: 'Crescimento acumulado mínimo (0–1)',
    CREEP_MIN_AVG:    'Ticket médio mínimo (R$) avaliado',
  }],
  ['Conciliação de Saldo OFX', {
    BALANCE_TOLERANCE:    'Diferença máxima (R$) tolerada',
    BALANCE_MAX_GAP_DAYS: 'Gap máximo (dias) entre extratos contíguos',
  }],
  ['Dormência', {
    DORMANT_MIN_GAP_DAYS:    'Dias sem débitos para conta dormente',
    DORMANT_BURST_DAYS:      'Janela (dias) da rajada',
    DORMANT_BURST_MIN_COUNT: 'Débitos mínimos na rajada',
    DORMANT_BURST_MIN_TOTAL: 'Total mínimo (R$) na rajada',
  }],
  ['Fim de Exercício', {
    YEAR_END_MIN_MONTHS: 'Meses de histórico mínimos',
    YEAR_END_RATIO:      'Razão dezembro ÷ média mensal',
  }],
  ['Score de Risco', {
    RISK_RECENT_WINDOW_DAYS:       'Janela (dias) de alerta "recente"',
    RISK_RECENT_BOOST:             'Multiplicador de alerta recente',
    RISK_STALE_DISCOUNT:           'Multiplicador de alerta antigo',
    RISK_CONCENTRATION_MIN_ALERTS: 'Alertas mínimos p/ desconto de concentração',
    RISK_CONCENTRATION_SHARE:      'Participação dominante (0–1)',
    RISK_CONCENTRATION_DISCOUNT:   'Multiplicador do desconto',
  }],
];

async function openConfigModal(accountId, accountName) {
  _configAccountId = accountId;
  document.getElementById('config-account-name').textContent = `Conta: ${accountName}`;
  document.getElementById('config-list-container').innerHTML = '<p class="empty-state">Carregando configuração…</p>';
  document.getElementById('config-modal').style.display = 'flex';
  await loadAccountConfig();
}
function closeConfigModal() { document.getElementById('config-modal').style.display = 'none'; _configAccountId = null; }

async function loadAccountConfig() {
  const c = document.getElementById('config-list-container');
  try {
    const r = await fetch(`${API}/accounts/${_configAccountId}/config`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error);
    const byKey = new Map(data.entries.map(e => [e.key, e]));

    let html = '';
    for (const [group, keys] of CONFIG_GROUPS) {
      const rows = Object.entries(keys).filter(([k]) => byKey.has(k));
      if (!rows.length) continue;
      html += `<p class="config-group-title">${group}</p>`;
      html += rows.map(([key, desc]) => {
        const e = byKey.get(key);
        const overridden = e.override !== null;
        return `
          <div class="config-row ${overridden ? 'config-row-overridden' : ''}">
            <div class="config-row-info">
              <span class="config-row-key">${key}</span>
              <span class="config-row-desc">${desc}</span>
            </div>
            <span class="config-row-default" title="Valor padrão">${e.default}</span>
            <input type="number" step="any" class="config-row-input" id="cfg-${key}" value="${e.effective}"/>
            <button class="btn-primary btn-sm" style="box-shadow:none;padding:4px 10px" title="Salvar" onclick="saveConfigKey('${key}')">💾</button>
            <button class="btn-ghost btn-sm" style="padding:4px 8px" title="Restaurar padrão" onclick="resetConfigKey('${key}')" ${overridden ? '' : 'disabled'}>↺</button>
          </div>`;
      }).join('');
    }
    c.innerHTML = html || '<p class="empty-state">Nenhuma configuração disponível.</p>';
  } catch (err) {
    c.innerHTML = `<p class="empty-state" style="color:var(--red)">Erro: ${escHtml(err.message)}</p>`;
  }
}

async function saveConfigKey(key) {
  const input = document.getElementById(`cfg-${key}`);
  const value = parseFloat(input?.value);
  if (isNaN(value)) { toast('Informe um número válido.', 'error'); return; }
  try {
    const r = await fetch(`${API}/accounts/${_configAccountId}/config`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    toast(`${key} salvo. Será aplicado na próxima análise.`, 'success');
    await loadAccountConfig();
  } catch (err) { toast('Erro ao salvar: ' + err.message, 'error'); }
}

async function resetConfigKey(key) {
  try {
    const r = await fetch(`${API}/accounts/${_configAccountId}/config/${encodeURIComponent(key)}`, { method: 'DELETE' });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    toast(`${key} restaurado ao padrão.`, 'info');
    await loadAccountConfig();
  } catch (err) { toast('Erro ao restaurar: ' + err.message, 'error'); }
}

async function saveAccount() {
  const name   = document.getElementById('acc-name').value.trim();
  const number = document.getElementById('acc-number').value.trim();
  if (!name || !number) { toast('Nome e número são obrigatórios','error'); return; }
  try {
    const r = await fetch(`${API}/accounts`, { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name, agency:document.getElementById('acc-agency').value.trim(),
        number, bank:document.getElementById('acc-bank').value.trim()||'Banco do Brasil',
        notes:document.getElementById('acc-notes').value.trim() }) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error);
    closeAccountModal();
    toast('Conta salva com sucesso!','success');
    loadAccounts();
  } catch(err) { toast('Erro: ' + err.message,'error'); }
}

async function deleteAccount(id) {
  if (!confirm('Remover esta conta e todo o histórico?')) return;
  await fetch(`${API}/accounts/${id}`, { method:'DELETE' });
  toast('Conta removida','info');
  loadAccounts();
}

// ── History ───────────────────────────────────────────────────
async function loadHistory() {
  const c = document.getElementById('history-container');
  try {
    const accounts = await fetch(`${API}/accounts`).then(r=>r.json());
    if (!accounts.length) { c.innerHTML='<p class="empty-state">Nenhuma conta cadastrada ainda.</p>'; return; }
    const scope = document.getElementById('history-scope')?.value || 'active';
    const scopedAccounts = scope === 'active' && state.activeAccountId
      ? accounts.filter(a => a.id === state.activeAccountId)
      : accounts;
    if (scope === 'active' && !state.activeAccountId) {
      c.innerHTML = '<p class="empty-state">Selecione uma conta para ver o historico dela.</p>';
      return;
    }
    let html = '';
    for (const acc of scopedAccounts) {
      const h = await fetch(`${API}/accounts/${acc.id}/history`).then(r=>r.json());
      if (!h.history?.length) continue;
      html += `<h2 class="sub-heading" style="margin-top:1.5rem">🏦 ${escHtml(acc.name)} — Conta ${acc.number}</h2>`;
      html += h.history.map(s=>`
        <div class="history-item">
          <div class="history-date">${formatDateBR(s.analyzed_at)}</div>
          <div class="history-meta">
            <div class="history-stat"><span class="history-stat-label">Transações</span><span class="history-stat-value">${s.tx_count}</span></div>
            <div class="history-stat"><span class="history-stat-label">Alertas</span><span class="history-stat-value">${s.alert_count}</span></div>
            <div class="history-stat"><span class="history-stat-label">Saldo Aplic.</span><span class="history-stat-value">R$ ${fmtM(s.last_balance)}</span></div>
            <div class="history-stat"><span class="history-stat-label">Período</span><span class="history-stat-value">${s.period_start||'?'} → ${s.period_end||'?'}</span></div>
          </div>
          <div class="history-badges">
            ${s.critical_count?`<span class="alert-count-badge badge-red">🔴 ${s.critical_count}</span>`:''}
            ${s.warning_count?`<span class="alert-count-badge badge-yellow">🟡 ${s.warning_count}</span>`:''}
            ${s.info_count?`<span class="alert-count-badge badge-cyan">🔵 ${s.info_count}</span>`:''}
          </div>
        </div>`).join('');
    }
    if (!html) { c.innerHTML='<p class="empty-state">Nenhuma análise anterior encontrada.</p>'; return; }
    c.innerHTML = html;
  } catch { c.innerHTML='<p class="empty-state">Erro ao carregar histórico.</p>'; }
}

// ── Resolve Alert ─────────────────────────────────────────────
function openResolveModal(alertId, title) {
  state.resolveAlertId = alertId;
  document.getElementById('resolve-alert-title').textContent = title;
  document.getElementById('resolve-note').value = '';
  document.getElementById('resolve-by').value = '';
  document.getElementById('resolve-modal').style.display = 'flex';
}
function closeResolveModal() { document.getElementById('resolve-modal').style.display='none'; }

async function confirmResolve() {
  const note = document.getElementById('resolve-note').value.trim();
  if (!note) { toast('Informe uma nota de resolução.','error'); return; }
  const by   = document.getElementById('resolve-by').value.trim() || 'Responsável';
  try {
    const r = await fetch(`${API}/alerts/${state.resolveAlertId}/resolve`, {
      method:'PATCH', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ note, resolvedBy:by }) });
    if (!r.ok) throw new Error('Erro ao resolver');
    // Update local state
    const a = state.alerts.find(a=>a.id===state.resolveAlertId);
    if (a) { a.resolved=true; a.resolution_note=note; }
    closeResolveModal();
    buildAlertsSection();
    updateAlertBadges();
    toast('Alerta marcado como resolvido!','success');
  } catch(err) { toast('Erro: ' + err.message,'error'); }
}

async function unresolveAlert(alertId) {
  await fetch(`${API}/alerts/${alertId}/unresolve`, { method:'PATCH' });
  const a = state.alerts.find(a=>a.id===alertId);
  if (a) { a.resolved=false; a.resolution_note=''; }
  buildAlertsSection();
  updateAlertBadges();
  toast('Alerta reaberto','info');
}

// #13 — Editor inline de nota
function openNoteEditor(alertId, currentNote) {
  // Remove any existing editor
  document.querySelectorAll('.note-inline-editor').forEach(e => e.remove());
  const display = document.getElementById(`note-display-${alertId}`);
  if (!display) return;
  const editor = document.createElement('div');
  editor.className = 'note-inline-editor';
  editor.id = `note-editor-${alertId}`;
  editor.innerHTML = `
    <input type="text" class="note-inline-input" id="note-input-${alertId}" value="${escHtml(currentNote)}" placeholder="Nova nota de resolução…" maxlength="500">
    <button class="note-inline-save" onclick="saveNote('${alertId}')">Salvar</button>
    <button class="note-inline-cancel" onclick="closeNoteEditor('${alertId}')">Cancelar</button>`;
  display.after(editor);
  document.getElementById(`note-input-${alertId}`)?.focus();
}

function closeNoteEditor(alertId) {
  document.getElementById(`note-editor-${alertId}`)?.remove();
}

async function saveNote(alertId) {
  const input = document.getElementById(`note-input-${alertId}`);
  const note  = input?.value.trim();
  if (!note) { toast('A nota não pode estar vazia.', 'error'); return; }
  try {
    const r = await fetch(`${API}/alerts/${alertId}/note`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    // Update local state
    const a = state.alerts.find(a => a.id === alertId);
    if (a) a.resolution_note = note;
    closeNoteEditor(alertId);
    buildAlertsSection();
    toast('Nota atualizada!', 'success');
  } catch (err) { toast('Erro ao salvar nota: ' + err.message, 'error'); }
}

// ── Busca Global (#2 paginação, #10 AbortController) ─────────
let _lastSearchResults = [];
let _lastSearchMemo    = '';
let _srchPage          = 1;
const SRCH_PAGE_SIZE   = 25;
let _searchController  = null;

function initSearchSection() {
  // Máscara automática DD/MM/AAAA
  document.querySelectorAll('.srch-date-input').forEach(el => {
    el.addEventListener('input', function() {
      let v = this.value.replace(/\D/g, '');
      if (v.length > 2) v = v.slice(0,2) + '/' + v.slice(2);
      if (v.length > 5) v = v.slice(0,5) + '/' + v.slice(5);
      this.value = v.slice(0, 10);
    });
  });
  // Enter para buscar em qualquer campo do painel
  document.getElementById('section-search')?.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('keydown', e => { if (e.key === 'Enter') runSearch(); });
  });
}

// Filtros rápidos
function applyPreset(name) {
  clearSearch(false); // limpa sem resetar o container
  const today = new Date();
  const fmt = d => `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`;
  switch (name) {
    case 'last30': {
      const from = new Date(today); from.setDate(from.getDate() - 30);
      document.getElementById('srch-from').value = fmt(from);
      document.getElementById('srch-to').value   = fmt(today);
      break;
    }
    case 'flagged':
      document.getElementById('srch-flagged').value = 'true'; break;
    case 'highValue':
      document.getElementById('srch-min').value = '1000'; break;
    case 'veryHigh':
      document.getElementById('srch-min').value = '10000'; break;
    case 'debits':
      document.getElementById('srch-type').value = 'debit'; break;
    case 'credits':
      document.getElementById('srch-type').value = 'credit'; break;
    case 'duplicates':
      document.getElementById('srch-flag').value = 'duplicate'; break;
    case 'weekend':
      document.getElementById('srch-flag').value = 'weekend_payment'; break;
    case 'skirting':
      document.getElementById('srch-flag').value = 'threshold_skirting'; break;
    case 'dormant':
      document.getElementById('srch-flag').value = 'dormant_burst'; break;
  }
  // Destacar chip ativo
  document.querySelectorAll('.preset-chip').forEach(b => b.classList.remove('active'));
  if (window.event && window.event.target) {
    window.event.target.classList.add('active');
  }
  runSearch();
}

function cancelSearch() {
  if (_searchController) {
    _searchController.abort();
    _searchController = null;
  }
  const btn = document.getElementById('btn-cancel-search');
  if (btn) btn.classList.remove('visible');
}

async function runSearch() {
  const btn = document.getElementById('btn-search');
  const cancelBtn = document.getElementById('btn-cancel-search');
  if (!btn) return;

  // #10 — AbortController com timeout de 30s
  if (_searchController) _searchController.abort();
  _searchController = new AbortController();
  const timeoutId = setTimeout(() => _searchController?.abort(), 30000);

  btn.disabled = true;
  btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> Buscando…';
  if (cancelBtn) cancelBtn.classList.add('visible');

  // #5 — Skeleton loading na busca
  document.getElementById('search-results-container').innerHTML =
    `<div style="display:flex;flex-direction:column;gap:6px">${Array(5).fill('<div class="skeleton skeleton-table-row"></div>').join('')}</div>`;

  try {
    const filters = {};
    const type = document.getElementById('srch-type').value;
    if (type && type !== 'both') filters.type = type;
    const amount = document.getElementById('srch-amount').value;
    if (amount) {
      filters.amount = parseFloat(amount);
      const tol = document.getElementById('srch-tolerance').value;
      if (tol) filters.amountTolerance = parseFloat(tol);
    }
    const min = document.getElementById('srch-min').value;
    const max = document.getElementById('srch-max').value;
    if (min) filters.amountMin = parseFloat(min);
    if (max) filters.amountMax = parseFloat(max);
    const memo = document.getElementById('srch-memo').value.trim();
    if (memo) { filters.memo = memo; _lastSearchMemo = memo; } else { _lastSearchMemo = ''; }
    const date = document.getElementById('srch-date').value.trim();
    if (date) filters.date = date;
    const from = document.getElementById('srch-from').value.trim();
    if (from) filters.dateFrom = from;
    const to = document.getElementById('srch-to').value.trim();
    if (to) filters.dateTo = to;
    const flag = document.getElementById('srch-flag').value;
    if (flag) filters.flag = flag;
    const flagged = document.getElementById('srch-flagged').value;
    if (flagged !== '') filters.flagged = flagged === 'true';
    const [sortBy, sortDir] = (document.getElementById('srch-sort').value || 'date|desc').split('|');
    filters.sortBy = sortBy; filters.sortDir = sortDir; filters.limit = 2000;

    const res  = await fetch(`${API}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filters),
      signal: _searchController.signal
    });
    clearTimeout(timeoutId);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erro na busca');
    _lastSearchResults = data.results || [];
    _srchPage = 1;
    renderSearchResults(data.results, data.summary);

    const csvBtn = document.getElementById('btn-export-csv');
    if (csvBtn) csvBtn.disabled = !data.results?.length;
  } catch(err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      document.getElementById('search-results-container').innerHTML =
        '<p class="empty-state">🚫 Busca cancelada.</p>';
    } else {
      document.getElementById('search-results-container').innerHTML =
        `<p class="empty-state" style="color:var(--red)">❌ Erro: ${escHtml(err.message)}</p>`;
    }
  } finally {
    clearTimeout(timeoutId);
    _searchController = null;
    btn.disabled = false;
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Buscar';
    if (cancelBtn) cancelBtn.classList.remove('visible');
  }
}

function clearSearch(resetContainer = true) {
  ['srch-amount','srch-tolerance','srch-min','srch-max','srch-memo','srch-date','srch-from','srch-to'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = id === 'srch-tolerance' ? '0.02' : '';
  });
  ['srch-type','srch-flag','srch-flagged','srch-sort'].forEach(id => {
    const el = document.getElementById(id); if (el) el.selectedIndex = 0;
  });
  document.querySelectorAll('.preset-chip').forEach(b => b.classList.remove('active'));
  document.getElementById('search-summary').style.display = 'none';
  const csvBtn = document.getElementById('btn-export-csv');
  if (csvBtn) csvBtn.disabled = true;
  _lastSearchResults = []; _lastSearchMemo = '';
  if (resetContainer) {
    document.getElementById('search-results-container').innerHTML =
      '<p class="empty-state">Use um <strong>filtro rápido</strong> ou preencha os campos acima e clique <kbd class="kbd-hint">Buscar</kbd>.</p>';
  }
}

function highlightMatch(text, query) {
  if (!query || !text) return escHtml(text || '');
  const safe = escHtml(text);
  const re = new RegExp(escHtml(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
  return safe.replace(re, m => `<mark class="srch-highlight">${m}</mark>`);
}

function renderSearchResults(results, summary) {
  const summaryEl = document.getElementById('search-summary');
  const container = document.getElementById('search-results-container');

  if (summary && summary.totalMatches > 0) {
    summaryEl.style.display = 'flex';
    summaryEl.innerHTML = `
      <span class="srch-stat"><strong>${summary.totalMatches}</strong> resultado(s)</span>
      <span class="srch-stat srch-stat-debit">↓ D: <strong>R$ ${fmtM(summary.totalDebits)}</strong></span>
      <span class="srch-stat srch-stat-credit">↑ C: <strong>R$ ${fmtM(summary.totalCredits)}</strong></span>
      <span class="srch-stat">Saldo: <strong style="color:${summary.netBalance>=0?'var(--green)':'var(--red)'}">R$ ${fmtM(summary.netBalance)}</strong></span>
      <span class="srch-stat">📁 <strong>${summary.accountCount}</strong> conta(s)</span>
      ${summary.flaggedCount?`<span class="srch-stat" style="color:var(--yellow)">⚠️ <strong>${summary.flaggedCount}</strong> suspeita(s)</span>`:''}`;
  } else { summaryEl.style.display = 'none'; }

  if (!results || !results.length) {
    container.innerHTML = '<p class="empty-state">🔍 Nenhum resultado. Tente outros filtros.</p>'; return;
  }

  _renderSrchPage(results, summary);
}

// #2 — Paginação da busca global
function _renderSrchPage(results, summary) {
  const container = document.getElementById('search-results-container');
  const total  = results.length;
  const pages  = Math.ceil(total / SRCH_PAGE_SIZE);
  const start  = (_srchPage - 1) * SRCH_PAGE_SIZE;
  const page   = results.slice(start, start + SRCH_PAGE_SIZE);

  const dirChip = r => r.direction === 'debit'
    ? '<span class="type-chip chip-debit">↓ DÉBITO</span>'
    : '<span class="type-chip chip-dep">↑ CRÉDITO</span>';
  const flagBadges = r => (r.flags||[]).map(f=>`<span class="flag-chip">${escHtml(f)}</span>`).join('');
  const initials = name => (name||'?').split(/\s+/).slice(0,2).map(w=>w[0]).join('').toUpperCase();
  const avatarColor = name => { let h = 0; for (const c of name||'') h = (h*31+c.charCodeAt(0))&0xffffffff; const colors = ['#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#f97316']; return colors[Math.abs(h)%colors.length]; };

  container.innerHTML = `
    <div class="data-table-wrap"><table class="data-table srch-table">
      <thead><tr>
        <th>Data</th><th>Tipo</th><th>Valor (R$)</th>
        <th>Conta</th><th>Descrição</th><th>Período</th><th>Flags</th>
      </tr></thead>
      <tbody>${page.map((r, i) => {
        const absIdx = start + i;
        const color = avatarColor(r.accountName||'');
        const ini   = initials(r.accountName||r.accountNumber||'?');
        const truncatedMemo = (r.memo || '').length > 80 ? (r.memo || '').substring(0, 80) + '…' : (r.memo || '');
        const memo  = highlightMatch(truncatedMemo, _lastSearchMemo);
        return `
        <tr class="${r.flagged?'flagged':''}" onclick="expandSearchRow(this,${absIdx})" style="cursor:pointer" title="Clique para expandir">
          <td style="white-space:nowrap;font-variant-numeric:tabular-nums">${escHtml(r.dateStr||'')}</td>
          <td>${dirChip(r)}</td>
          <td class="${r.direction==='debit'?'amount-neg':'amount-pos'}" style="font-variant-numeric:tabular-nums">${fmtM(r.absAmount)}</td>
          <td>
            <div class="srch-account-cell">
              <span class="srch-avatar" style="background:${color}">${ini}</span>
              <span class="srch-account-info">
                <span class="srch-account-num">${escHtml(r.accountNumber||'')}</span>
                ${r.accountName?`<span class="srch-account-name">${escHtml(r.accountName)}</span>`:''}
              </span>
            </div>
          </td>
          <td class="srch-memo-cell"><span class="srch-memo-short">${memo}</span></td>
          <td style="font-size:.73rem;color:var(--text-3)">${escHtml(r.period||'')}</td>
          <td>${flagBadges(r)}${r.flagged&&!r.flags?.length?'<span class="flag-chip">⚠️</span>':''}</td>
        </tr>
        <tr class="srch-expand-row" id="srch-expand-${absIdx}" style="display:none">
          <td colspan="7" class="srch-expand-cell">
            <div class="srch-expand-body">
              <div><strong>Memo completo:</strong><br><span style="font-family:monospace;font-size:.8rem">${escHtml(r.memo||'')}</span></div>
              ${r.beneficiary&&r.beneficiary!=='Outros'?`<div><strong>Beneficiário:</strong><br>${escHtml(r.beneficiary)}</div>`:''}
              <div><strong>ID:</strong><br><span style="font-family:monospace;font-size:.75rem;color:var(--text-3)">${escHtml(r.id||'')}</span></div>
              <div><strong>Conta:</strong><br>${escHtml(r.accountName||'')} (${escHtml(r.accountNumber||'')})</div>
            </div>
          </td>
        </tr>`;
      }).join('')}
      </tbody>
    </table></div>
    <p style="margin-top:.5rem;font-size:.78rem;color:var(--text-3)">${total} resultado(s) — página ${_srchPage} de ${pages}</p>
    ${pages > 1 ? _srchPagination(pages) : ''}`;
}

function _srchPagination(pages) {
  let html = '<div class="srch-pagination">';
  html += `<button class="srch-page-btn" ${_srchPage<=1?'disabled':''} onclick="goSrchPage(${_srchPage-1})">‹ Anterior</button>`;
  const start = Math.max(1, _srchPage - 2);
  const end   = Math.min(pages, _srchPage + 2);
  if (start > 1) html += `<button class="srch-page-btn" onclick="goSrchPage(1)">1</button>${start > 2 ? '<span style="color:var(--text-3);padding:0 4px">…</span>' : ''}`;
  for (let i = start; i <= end; i++) {
    html += `<button class="srch-page-btn ${i===_srchPage?'active':''}" onclick="goSrchPage(${i})">${i}</button>`;
  }
  if (end < pages) html += `${end < pages - 1 ? '<span style="color:var(--text-3);padding:0 4px">…</span>' : ''}<button class="srch-page-btn" onclick="goSrchPage(${pages})">${pages}</button>`;
  html += `<button class="srch-page-btn" ${_srchPage>=pages?'disabled':''} onclick="goSrchPage(${_srchPage+1})">Próxima ›</button>`;
  html += '</div>';
  return html;
}

function goSrchPage(p) {
  _srchPage = p;
  _renderSrchPage(_lastSearchResults);
  window.scrollTo({ top: document.getElementById('section-search')?.offsetTop || 0, behavior: 'smooth' });
}

function expandSearchRow(row, idx) {
  const exp = document.getElementById(`srch-expand-${idx}`);
  if (!exp) return;
  const isOpen = exp.style.display !== 'none';
  exp.style.display = isOpen ? 'none' : 'table-row';
  row.classList.toggle('srch-row-expanded', !isOpen);
}

function exportSearchCSV() {
  if (!_lastSearchResults.length) { toast('Faça uma busca primeiro.','error'); return; }
  const headers = ['Data','Tipo','Valor','Conta','Numero','Descricao','Beneficiario','Periodo','Flags','Flagged'];
  const rows = _lastSearchResults.map(r => [
    r.dateStr||'',
    r.direction==='debit'?'DEBITO':'CREDITO',
    (r.absAmount||0).toFixed(2),
    r.accountName||'',
    r.accountNumber||'',
    (r.memo||'').replace(/"/g,'""'),
    (r.beneficiary||'').replace(/"/g,'""'),
    r.period||'',
    (r.flags||[]).join(';'),
    r.flagged?'SIM':'NAO'
  ].map(v=>`"${v}"`).join(',')).join('\n');
  const bom = '\uFEFF';
  const blob = new Blob([bom + headers.join(',') + '\n' + rows], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.setAttribute('download', `busca_transacoes_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// ── Export ────────────────────────────────────────────────────
function exportExcel() {
  if (!state.sessionId) { toast('Execute a análise primeiro.','error'); return; }
  window.open(`${API}/export/excel/${state.sessionId}`, '_blank');
}
function exportPDF() {
  if (!state.sessionId) { toast('Execute a análise primeiro.','error'); return; }
  window.open(`${API}/export/pdf/${state.sessionId}`, '_blank');
}

// ── Helpers ───────────────────────────────────────────────────
function fmtM(v) { return (v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtBytes(b) { return b<1024?b+' B':b<1048576?(b/1024).toFixed(1)+' KB':(b/1048576).toFixed(1)+' MB'; }
function escHtml(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function sleep(ms) { return new Promise(r=>setTimeout(r,ms)); }
function formatDateBR(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

// #4 — Loader com steps
function showLoader(msg, pct=0, step=0, totalSteps=0) {
  document.getElementById('loader-msg').textContent = msg;
  setProgress(pct);
  document.getElementById('loading-overlay').style.display = 'flex';
  setStatusBadge('loading','Processando…');
  const stepsEl = document.getElementById('loader-steps');
  if (stepsEl && totalSteps > 0) {
    stepsEl.style.display = 'flex';
    for (let i = 1; i <= 3; i++) {
      const s = document.getElementById(`lstep-${i}`);
      if (!s) continue;
      s.className = 'loader-step' + (i < step ? ' done' : i === step ? ' active' : '');
    }
  } else if (stepsEl) {
    stepsEl.style.display = 'none';
  }
}
function updateLoader(msg, step=0, totalSteps=0) {
  document.getElementById('loader-msg').textContent = msg;
  if (step > 0) showLoader(msg, undefined, step, totalSteps || 3);
}
function hideLoader()      {
  document.getElementById('loading-overlay').style.display = 'none';
  const stepsEl = document.getElementById('loader-steps');
  if (stepsEl) stepsEl.style.display = 'none';
}
function setProgress(pct)  {
  const el = document.getElementById('progress-bar');
  if (el) el.style.width = pct + '%';
}
function setStatusBadge(type, text) {
  const el = document.getElementById('header-status');
  el.className = 'status-badge status-' + type;
  el.textContent = text;
}

function lineOpts(y1, y2) {
  return { responsive:true, interaction:{ mode:'index', intersect:false },
    plugins:{ legend:{ labels:{ color:'#94a3b8', font:{ size:11, family:'Inter' } } } },
    scales:{
      x:{ grid:{ color:'rgba(255,255,255,.05)' }, ticks:{ color:'#64748b', font:{size:10} } },
      y:{ grid:{ color:'rgba(255,255,255,.05)' }, ticks:{ color:'#64748b', font:{size:10}, callback:v=>'R$'+fmtK(v) } },
      ...(y2 ? { y2:{ position:'right', grid:{ drawOnChartArea:false }, ticks:{ color:'#10b981', font:{size:10}, callback:v=>'R$'+fmtK(v) } } } : {})
    }};
}
function barOpts() {
  return { responsive:true, plugins:{ legend:{ labels:{ color:'#94a3b8', font:{size:11} } } },
    scales:{
      x:{ grid:{ color:'rgba(255,255,255,.05)' }, ticks:{ color:'#64748b', font:{size:10} } },
      y:{ grid:{ color:'rgba(255,255,255,.05)' }, ticks:{ color:'#64748b', font:{size:10}, callback:v=>'R$'+fmtK(v) } }
    }};
}
function fmtK(v) { return v>=1000000?(v/1000000).toFixed(1)+'M':v>=1000?(v/1000).toFixed(0)+'k':v.toFixed(0); }

function updateAlertBadges() {
  const unresolved = state.alerts.filter(a => !a.resolved);
  const unresolvedCount = unresolved.length;
  const badge = document.getElementById('alerts-badge');
  if (badge) {
    if (unresolvedCount) {
      badge.textContent = unresolvedCount;
      badge.style.display = 'flex';
    } else {
      badge.style.display = 'none';
    }
  }

  // Also update KPI cards if they are on screen
  if (state.stats) {
    const criticalUnresolved = unresolved.filter(a => a.severity === 'critical').length;
    const warningUnresolved = unresolved.filter(a => a.severity === 'warning').length;
    
    // Find the Alertas KPI card and update its content
    const kpiCards = document.querySelectorAll('.kpi-card');
    for (const card of kpiCards) {
      const label = card.querySelector('.kpi-label')?.textContent?.trim();
      if (label === 'Alertas') {
        const valSpan = card.querySelector('.kpi-value');
        const subSpan = card.querySelector('.kpi-sub');
        if (valSpan) valSpan.innerHTML = `${criticalUnresolved}🔴 ${warningUnresolved}🟡`;
        if (subSpan) subSpan.textContent = `${unresolvedCount} não resolvida(s) de ${state.alerts.length}`;
      }
    }
  }
  renderActiveContext();
}

let crossData = null;

async function loadCrossAnalysis() {
  const recContainer = document.getElementById('cross-reconciled-container');
  const discContainer = document.getElementById('cross-discrepancies-container');
  const dupContainer = document.getElementById('cross-duplicates-container');
  const smurfContainer = document.getElementById('cross-smurfing-container');

  if (recContainer) recContainer.innerHTML = '<p class="empty-state">Buscando cruzamento de dados no SQLite...</p>';
  if (discContainer) discContainer.innerHTML = '<p class="empty-state">Buscando cruzamento de dados no SQLite...</p>';
  if (dupContainer) dupContainer.innerHTML = '<p class="empty-state">Buscando cruzamento de dados no SQLite...</p>';
  if (smurfContainer) smurfContainer.innerHTML = '<p class="empty-state">Buscando cruzamento de dados no SQLite...</p>';

  try {
    const scope = document.getElementById('cross-scope')?.value || 'all';
    const qs = scope === 'active' && state.activeAccountId ? `?accountId=${encodeURIComponent(state.activeAccountId)}` : '';
    const label = document.getElementById('cross-scope-label');
    if (label) label.textContent = scope === 'active' && state.activeAccount
      ? `Filtrando achados que envolvem ${state.activeAccount.name} (${state.activeAccount.number}).`
      : 'Usando a ultima sessao de cada conta.';
    const r = await fetch(`${API}/cross-analysis${qs}`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error);

    crossData = data;

    // Update KPIs
    document.getElementById('cross-stat-accounts').textContent = data.summary.accountsCount;
    document.getElementById('cross-stat-reconciled').textContent = data.summary.reconciledCount;
    document.getElementById('cross-stat-discrepancies').textContent = data.summary.discrepanciesCount;
    document.getElementById('cross-stat-duplicates').textContent = data.summary.duplicatesCount;
    document.getElementById('cross-stat-smurfing').textContent = data.summary.smurfingCount;
    
    // Render reconciled transfers panel
    if (!data.reconciled.length) {
      recContainer.innerHTML = '<p class="empty-state">Nenhuma transferência própria mapeada e conciliada.</p>';
    } else {
      recContainer.innerHTML = `
        <div class="data-table-wrap">
          <table class="data-table">
            <thead><tr>
              <th>Origem</th>
              <th>Fluxo</th>
              <th>Destino</th>
              <th>Data do Envio</th>
              <th>Valor Conciliado</th>
            </tr></thead>
            <tbody>
              ${data.reconciled.map(rec => `
                <tr>
                  <td>
                    <strong>${escHtml(rec.origin.name)}</strong><br/>
                    <span style="font-size:0.7rem;color:var(--text-3)">Conta: ${rec.origin.number}</span>
                  </td>
                  <td>
                    <span style="color:var(--green);font-weight:bold;">──[ R$ ${fmtM(rec.amount)} ]──></span>
                  </td>
                  <td>
                    <strong>${escHtml(rec.dest.name)}</strong><br/>
                    <span style="font-size:0.7rem;color:var(--text-3)">Conta: ${rec.dest.number}</span>
                  </td>
                  <td>${rec.dateStr}</td>
                  <td class="amount-pos">R$ ${fmtM(rec.amount)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>`;
    }
    
    // Render flow discrepancies panel
    if (!data.discrepancies.length) {
      discContainer.innerHTML = '<p class="empty-state">Nenhuma divergência de fluxo intercontas própria identificada.</p>';
    } else {
      discContainer.innerHTML = `
        <div class="data-table-wrap">
          <table class="data-table">
            <thead><tr>
              <th>Tipo de Erro</th>
              <th>Conta Afetada</th>
              <th>Data</th>
              <th>Valor</th>
              <th>Descrição da Inconsistência</th>
            </tr></thead>
            <tbody>
              ${data.discrepancies.map(disc => {
                const isOut = disc.type === 'Saída sem Entrada';
                const acc = isOut ? disc.origin : disc.dest;
                return `
                  <tr>
                    <td>
                      <span class="type-chip chip-debit" style="font-size:0.65rem;">${escHtml(disc.type)}</span>
                    </td>
                    <td>
                      <strong>${escHtml(acc.name)}</strong><br/>
                      <span style="font-size:0.7rem;color:var(--text-3)">Conta: ${acc.number}</span>
                    </td>
                    <td>${disc.dateStr}</td>
                    <td class="amount-neg">R$ ${fmtM(disc.amount)}</td>
                    <td style="white-space:normal; font-size:0.78rem; line-height:1.4; color:var(--text-2)">
                      ${escHtml(disc.description)}<br/>
                      <span style="font-size:0.68rem;color:var(--text-3);font-style:italic;">Memo: "${escHtml(acc.memo)}"</span>
                    </td>
                  </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>`;
    }
    
    // Render cross duplicates panel
    if (!data.duplicates.length) {
      dupContainer.innerHTML = '<p class="empty-state">Nenhum pagamento duplicado cruzado (contas diferentes) identificado.</p>';
    } else {
      dupContainer.innerHTML = `
        <div class="data-table-wrap">
          <table class="data-table">
            <thead><tr>
              <th>Valor Duplicado</th>
              <th>Conta Origem A</th>
              <th>Conta Origem B</th>
              <th>Histórico (Memos)</th>
              <th>Diferença de Dias</th>
            </tr></thead>
            <tbody>
              ${data.duplicates.map(dup => `
                <tr class="flagged">
                  <td class="amount-neg" style="font-size: 0.9rem; font-weight: bold; border-left: 3px solid var(--red);">
                    R$ ${fmtM(dup.amount)}
                  </td>
                  <td>
                    <strong>${escHtml(dup.tx1.name)}</strong><br/>
                    <span style="font-size:0.7rem;color:var(--text-3)">Conta: ${dup.tx1.number}</span><br/>
                    <span style="font-size:0.7rem;color:var(--text-2)">Data: ${dup.tx1.dateStr}</span>
                  </td>
                  <td>
                    <strong>${escHtml(dup.tx2.name)}</strong><br/>
                    <span style="font-size:0.7rem;color:var(--text-3)">Conta: ${dup.tx2.number}</span><br/>
                    <span style="font-size:0.7rem;color:var(--text-2)">Data: ${dup.tx2.dateStr}</span>
                  </td>
                  <td style="white-space:normal; font-size:0.78rem; line-height:1.4;">
                    <span style="color:var(--yellow)">Conta A:</span> "${escHtml(dup.tx1.memo)}"<br/>
                    <span style="color:var(--cyan)">Conta B:</span> "${escHtml(dup.tx2.memo)}"
                  </td>
                  <td style="font-weight: 500;">
                    ${dup.daysDiff === 0 ? 'Mesmo dia' : `${dup.daysDiff.toFixed(0)} dia(s)`}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>`;
    }

    // Render cross-account structuring ("fracionamento") panel
    if (!data.smurfing || !data.smurfing.length) {
      smurfContainer.innerHTML = '<p class="empty-state">Nenhum indício de fracionamento entre contas identificado.</p>';
    } else {
      smurfContainer.innerHTML = `
        <div class="data-table-wrap">
          <table class="data-table">
            <thead><tr>
              <th>Beneficiário (referência)</th>
              <th>Contas Envolvidas</th>
              <th>Período</th>
              <th>Qtd. Pagamentos</th>
              <th>Total Agregado</th>
              <th>Indício</th>
            </tr></thead>
            <tbody>
              ${data.smurfing.map(sm => `
                <tr class="flagged">
                  <td><strong>${escHtml(sm.beneficiary)}</strong></td>
                  <td style="white-space:normal; font-size:0.78rem; line-height:1.5;">
                    ${sm.items.map(it => `${escHtml(it.name)} <span style="color:var(--text-3)">(Conta ${it.number})</span> — R$ ${fmtM(it.amount)} em ${it.dateStr}`).join('<br/>')}
                  </td>
                  <td>${sm.startDateStr} – ${sm.endDateStr}</td>
                  <td>${sm.itemsCount} pagtos / ${sm.accountsCount} contas</td>
                  <td class="amount-neg" style="font-weight:bold;">R$ ${fmtM(sm.total)}</td>
                  <td style="white-space:normal; font-size:0.78rem; line-height:1.4; color:var(--text-2)">
                    ${escHtml(sm.reason)}<br/>
                    <span style="font-size:0.68rem;color:var(--text-3);font-style:italic;">CV: ${sm.cv}</span>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>`;
    }

  } catch (err) {
    console.error('Erro no carregamento da análise cruzada:', err);
    const errorMsg = `<p class="empty-state" style="color:var(--red)">Erro ao carregar análise cruzada: ${err.message}</p>`;
    if (recContainer) recContainer.innerHTML = errorMsg;
    if (discContainer) discContainer.innerHTML = errorMsg;
    if (dupContainer) dupContainer.innerHTML = errorMsg;
    if (smurfContainer) smurfContainer.innerHTML = errorMsg;
  }
}

function setCrossTab(tabName) {
  document.querySelectorAll('.cross-panel').forEach(p => p.style.display = 'none');
  document.getElementById(`cross-panel-${tabName}`).style.display = 'block';
  document.querySelectorAll('[id^="tab-btn-"]').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`tab-btn-${tabName}`).classList.add('active');
}

// ── CSV Export (#6) ───────────────────────────────────────────
function exportCSV() {
  if (!state.sessionId) { toast('Execute a análise primeiro.', 'error'); return; }
  window.open(`${API}/export/csv/${state.sessionId}`, '_blank');
}

// ── Daily Balance Chart (#0) ──────────────────────────────────
function buildDailyBalanceChart() {
  const daily = state.stats?.dailyBalance || [];
  if (!daily.length) return;
  if (state.charts.dailyBal) state.charts.dailyBal.destroy();
  const ctx = document.getElementById('chart-daily-balance')?.getContext('2d');
  if (!ctx) return;
  state.charts.dailyBal = new Chart(ctx, {
    type: 'line',
    data: {
      labels: daily.map(d => d.date),
      datasets: [{
        label: 'Saldo Diário (R$)',
        data: daily.map(d => d.balance),
        borderColor: '#06b6d4',
        backgroundColor: 'rgba(6,182,212,.08)',
        borderWidth: 2,
        pointRadius: 0,
        tension: .3,
        fill: true
      }]
    },
    options: lineOpts('Saldo (R$)', '')
  });
}

// ── Weekday Heatmap (#6 — gradiente dinâmico HSL) ─────────────
function buildWeekdayHeatmap() {
  const dist = state.stats?.weekdayDistribution;
  if (!dist || !dist.some(v => v > 0)) return;
  const days = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
  const max  = Math.max(...dist, 1);
  const el   = document.getElementById('weekday-heatmap');
  if (!el) return;
  el.innerHTML = `<div class="heatmap-row">` +
    days.map((d, i) => {
      const pct = dist[i] / max;
      // HSL: 0 = red (high volume), 130 = green (low), intermediate yellow
      const hue   = Math.round(130 - pct * 130);
      const sat   = 70;
      const light = 35 + (1 - pct) * 20;
      const alpha = (0.12 + pct * 0.78).toFixed(2);
      const bg    = pct > 0.05
        ? `hsla(${hue},${sat}%,${light}%,${alpha})`
        : 'rgba(255,255,255,0.03)';
      return `<div class="heatmap-cell" title="${d}: R$ ${fmtM(dist[i])}">
        <div class="heatmap-fill" style="background:${bg}"></div>
        <span class="heatmap-label">${d}</span>
        <span class="heatmap-val">R$ ${fmtK(dist[i])}</span>
      </div>`;
    }).join('') + `</div>`;
}

// ── Risk Score Bar (#1) ───────────────────────────────────────
function buildRiskScoreBar() {
  const score = state.stats?.riskScore ?? null;
  const el    = document.getElementById('risk-score-bar');
  if (!el || score === null) return;
  const color = score >= 70 ? 'var(--red)' : score >= 40 ? 'var(--yellow)' : 'var(--green)';
  const label = score >= 70 ? 'Alto Risco' : score >= 40 ? 'Risco Moderado' : 'Baixo Risco';
  el.style.display = 'block';
  el.innerHTML = `
    <div class="risk-bar-wrap">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem">
        <span style="font-size:.75rem;font-weight:700;color:var(--text-3);text-transform:uppercase;letter-spacing:.5px">Score de Risco</span>
        <span style="font-size:.875rem;font-weight:700;color:${color}">${label} — ${score}/100</span>
      </div>
      <div style="height:8px;background:var(--border);border-radius:99px;overflow:hidden">
        <div style="width:${score}%;height:100%;background:${color};border-radius:99px;transition:width .6s ease"></div>
      </div>
    </div>`;
}

// ── Fund Evolution Chart (#16) ────────────────────────────────
function buildFundEvolutionChart() {
  const inv = (state.stats?.monthlyInvestments || []).sort((a, b) => (a.periodSort || '').localeCompare(b.periodSort || ''));
  const card = document.getElementById('fund-chart-card');
  if (!inv.length) { if (card) card.style.display = 'none'; return; }
  if (card) card.style.display = 'block';
  if (state.charts.fundEvo) state.charts.fundEvo.destroy();
  const ctx = document.getElementById('chart-fund-evolution')?.getContext('2d');
  if (!ctx) return;
  state.charts.fundEvo = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: inv.map(i => i.period),
      datasets: [
        { label: 'Saldo do Fundo (R$)', data: inv.map(i => i.saldoAtual), backgroundColor: 'rgba(99,102,241,.7)', borderRadius: 5, yAxisID: 'y' },
        { label: 'Rendimento Bruto (R$)', data: inv.map(i => i.rendBruto), backgroundColor: 'rgba(16,185,129,.7)', borderRadius: 5, yAxisID: 'y' }
      ]
    },
    options: barOpts()
  });
}


// ── Advanced Transaction Filters (#9) — replaces filterTransactions inline ──
function clearTxFilters() {
  document.getElementById('tx-search').value = '';
  document.getElementById('tx-type-filter').value = '';
  document.getElementById('tx-month-filter').value = '';
  document.getElementById('tx-flag-filter').value = '';
  document.getElementById('tx-min-value').value = '';
  document.getElementById('tx-max-value').value = '';
  document.getElementById('tx-direction-filter').value = '';
  filterTransactions();
}

function filterTransactions() {
  const search    = document.getElementById('tx-search').value.toLowerCase();
  const type      = document.getElementById('tx-type-filter').value;
  const month     = document.getElementById('tx-month-filter').value;
  const flagged   = document.getElementById('tx-flag-filter').value;
  const minVal    = parseFloat(document.getElementById('tx-min-value')?.value) || null;
  const maxVal    = parseFloat(document.getElementById('tx-max-value')?.value) || null;
  const direction = document.getElementById('tx-direction-filter')?.value || '';

  state.txFiltered = state.transactions.filter(t => {
    if (search && !(t.memo || '').toLowerCase().includes(search) &&
        !String(Math.abs(t.amount)).includes(search) &&
        !(t.dateStr || '').includes(search)) return false;
    if (type && t.type !== type) return false;
    if (month && (t.dateStr || '').substring(3) !== month) return false;
    if (flagged === 'flagged' && !t.flagged) return false;
    if (flagged && flagged !== 'flagged' && !(t.flags || []).includes(flagged)) return false;
    if (minVal !== null && Math.abs(t.amount) < minVal) return false;
    if (maxVal !== null && Math.abs(t.amount) > maxVal) return false;
    if (direction === 'credit' && t.amount < 0) return false;
    if (direction === 'debit'  && t.amount >= 0) return false;
    return true;
  });
  state.txPage = 1;
  renderPage();
}

// ── Compare Periods (#8) ──────────────────────────────────────
async function loadCompareSessions() {
  const sel1 = document.getElementById('compare-session-1');
  const sel2 = document.getElementById('compare-session-2');
  if (!sel1 || !sel2) return;
  try {
    const accounts = await fetch(`${API}/accounts`).then(r => r.json());
    let options = '<option value="">Selecione…</option>';
    for (const acc of accounts) {
      const h = await fetch(`${API}/accounts/${acc.id}/history`).then(r => r.json());
      for (const s of (h.history || [])) {
        const label = `${acc.name} — ${s.period_start || '?'} → ${s.period_end || '?'} (${s.analyzed_at?.substring(0, 16) || ''})`;
        options += `<option value="${escHtml(s.id)}">${escHtml(label)}</option>`;
      }
    }
    sel1.innerHTML = options;
    sel2.innerHTML = options;
    if (state.sessionId) {
      sel2.value = state.sessionId;
    }
  } catch (err) { console.error('Erro ao carregar sessões para comparação:', err); }
}

async function runComparison() {
  const sid1 = document.getElementById('compare-session-1').value;
  const sid2 = document.getElementById('compare-session-2').value;
  const c    = document.getElementById('compare-result-container');
  if (!sid1 || !sid2) { toast('Selecione as duas sessões.', 'error'); return; }
  if (sid1 === sid2) { toast('Selecione sessões diferentes.', 'error'); return; }
  try {
    const r = await fetch(`${API}/sessions/${sid1}/compare/${sid2}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    renderComparisonResult(d, c);
  } catch (err) { c.innerHTML = `<p class="empty-state" style="color:var(--red)">Erro: ${err.message}</p>`; }
}

async function loadCompareCurrentDelta() {
  if (!state.sessionId) { toast('Execute uma análise primeiro.', 'error'); return; }
  const c = document.getElementById('compare-result-container');
  try {
    const r = await fetch(`${API}/sessions/${state.sessionId}/delta`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    if (!d.hasPrevious) { c.innerHTML = `<p class="empty-state">${escHtml(d.message || 'Não há análise anterior.')}</p>`; return; }
    renderComparisonResult(d, c, `Sessão anterior — ${(d.previousDate || '').substring(0, 16)}`);
  } catch (err) { c.innerHTML = `<p class="empty-state" style="color:var(--red)">Erro: ${err.message}</p>`; }
}

function renderComparisonResult(d, container, baseLabel) {
  const diff  = d.diff || {};
  const sign  = v => (v > 0 ? '+' : '') + fmtM(v);
  const color = v => v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--text-3)';
  const kpis  = [
    ['Transações',       diff.totalTransactions, ''],
    ['Entradas (R$)',    diff.totalCredits,       'R$ '],
    ['Saídas (R$)',      diff.totalDebits,        'R$ '],
    ['Alertas',          diff.totalAlerts,        ''],
    ['Críticos',         diff.criticalAlerts,     ''],
    ['Saldo Aplicação',  diff.lastBalance,        'R$ '],
    ['Score de Risco',   diff.riskScore,          ''],
  ];
  let html = `<h2 class="sub-heading">${baseLabel ? `Comparação: Atual vs ${escHtml(baseLabel)}` : 'Resultado da Comparação'}</h2>
    <div class="kpi-grid" style="margin-bottom:1.5rem">
      ${kpis.map(([lbl, val, prefix]) => `
        <div class="kpi-card" style="--kpi-color:${color(val)}">
          <span class="kpi-label">${lbl}</span>
          <span class="kpi-value" style="color:${color(val)};font-size:1.2rem">${prefix}${sign(val || 0)}</span>
        </div>`).join('')}
    </div>`;
  if (d.newAlerts?.length) {
    html += `<h2 class="sub-heading" style="margin-top:1.5rem">🆕 Novos Alertas (${d.newAlerts.length})</h2>`;
    html += d.newAlerts.map(a => `
      <div class="alert-item alert-${a.severity}" style="margin-bottom:.5rem">
        <span class="alert-icon">${a.icon || '⚠️'}</span>
        <div class="alert-body">
          <p class="alert-title">${escHtml(a.title)}</p>
          <p class="alert-desc">${escHtml(a.description?.substring(0, 120))}</p>
        </div>
      </div>`).join('');
  } else {
    html += `<p style="color:var(--green);font-size:.875rem;margin-top:1rem">✓ Nenhum alerta novo nesta comparação.</p>`;
  }
  container.innerHTML = html;
}

// ── Audit Trail (#14) ─────────────────────────────────────────
async function initAuditTrail() {
  const sel = document.getElementById('audit-account-select');
  if (!sel) return;
  try {
    const accounts = await fetch(`${API}/accounts`).then(r => r.json());
    sel.innerHTML = '<option value="">Selecione uma conta…</option>' +
      accounts.map(a => `<option value="${escHtml(a.id)}">${escHtml(a.name)} (${a.number})</option>`).join('');
    // Pre-select current account if available
    if (state.stats?.topBeneficiaries && state.sessionId) {
      const r = await fetch(`${API}/sessions/${state.sessionId}`);
      const d = await r.json();
      if (d.account?.id) { sel.value = d.account.id; loadAuditTrail(d.account.id); }
    }
  } catch (err) { console.error('Erro ao inicializar trilha de auditoria:', err); }
}

async function loadAuditTrail(accountId) {
  const c = document.getElementById('audit-container');
  if (!accountId) { c.innerHTML = '<p class="empty-state">Selecione uma conta.</p>'; return; }
  try {
    const r = await fetch(`${API}/audit/${accountId}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    if (!d.events.length) { c.innerHTML = '<p class="empty-state">Nenhum evento encontrado para esta conta.</p>'; return; }
    c.innerHTML = `<div class="audit-timeline">` +
      d.events.map(ev => {
        const icon  = ev.type === 'analysis' ? '🔍' : ev.type === 'resolve' ? '✅' : '📌';
        const color = ev.type === 'analysis' ? 'var(--primary)' : ev.type === 'resolve' ? 'var(--green)' : 'var(--yellow)';
        return `<div class="audit-event">
          <div class="audit-dot" style="background:${color}">${icon}</div>
          <div class="audit-event-body">
            <p class="audit-event-desc">${escHtml(ev.description)}</p>
            ${ev.meta?.note ? `<p class="audit-event-note">${escHtml(ev.meta.note.substring(0, 100))}</p>` : ''}
            <span class="audit-event-ts">${formatDateBR(ev.timestamp)}</span>
          </div>
        </div>`;
      }).join('') + `</div>`;
  } catch (err) { c.innerHTML = `<p class="empty-state" style="color:var(--red)">Erro: ${err.message}</p>`; }
}

// ── Alert Attachments (#10) ───────────────────────────────────
let _attachAlertId = null;

function openAttachModal(alertId, title) {
  _attachAlertId = alertId;
  document.getElementById('attach-alert-title').textContent = title;
  document.getElementById('attach-file-input').value = '';
  document.getElementById('attach-note').value = '';
  loadAttachmentList(alertId);
  document.getElementById('attach-modal').style.display = 'flex';
}
function closeAttachModal() { document.getElementById('attach-modal').style.display = 'none'; }

async function uploadAttachment() {
  const file = document.getElementById('attach-file-input').files[0];
  if (!file) { toast('Selecione um arquivo.', 'error'); return; }
  const note = document.getElementById('attach-note').value.trim();
  const form = new FormData();
  form.append('file', file);
  form.append('note', note);
  try {
    const r = await fetch(`${API}/alerts/${_attachAlertId}/attachments`, { method: 'POST', body: form });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    toast('Arquivo anexado com sucesso!', 'success');
    document.getElementById('attach-file-input').value = '';
    document.getElementById('attach-note').value = '';
    loadAttachmentList(_attachAlertId);
  } catch (err) { toast('Erro ao anexar: ' + err.message, 'error'); }
}

async function loadAttachmentList(alertId) {
  const c = document.getElementById('attach-list-container');
  try {
    const r = await fetch(`${API}/alerts/${alertId}/attachments`);
    const list = await r.json();
    if (!list.length) { c.innerHTML = '<p style="font-size:.78rem;color:var(--text-3)">Nenhum anexo ainda.</p>'; return; }
    c.innerHTML = `<p style="font-size:.75rem;font-weight:700;color:var(--text-3);margin-bottom:.5rem">ANEXOS (${list.length})</p>` +
      list.map(a => `
        <div style="display:flex;align-items:center;gap:.5rem;padding:.4rem .6rem;background:var(--bg-card2);border-radius:var(--radius-sm);margin-bottom:.25rem">
          <span style="font-size:.8rem;flex:1;color:var(--text-1)">${escHtml(a.filename)}</span>
          <span style="font-size:.7rem;color:var(--text-3)">${fmtBytes(a.size || 0)}</span>
          <a href="${API}/attachments/${a.id}" target="_blank" class="btn-ghost btn-sm" style="padding:2px 8px">⬇️</a>
        </div>`).join('');
  } catch { c.innerHTML = ''; }
}

// ── Email Summary (#18) ───────────────────────────────────────
async function generateEmailSummary() {
  if (!state.sessionId) { toast('Execute a análise primeiro.', 'error'); return; }
  try {
    const r = await fetch(`${API}/sessions/${state.sessionId}/email-summary`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    document.getElementById('email-subject').value = d.subject;
    document.getElementById('email-body').value    = d.text;
    document.getElementById('email-modal').style.display = 'flex';
  } catch (err) { toast('Erro ao gerar resumo: ' + err.message, 'error'); }
}
function closeEmailModal() { document.getElementById('email-modal').style.display = 'none'; }
function copyEmailBody() {
  const el = document.getElementById('email-body');
  el.select();
  document.execCommand('copy');
  toast('Corpo do e-mail copiado!', 'success');
}

// ── Attach button injected after alerts render ────────────────
function injectAttachButtons() {
  // Inject "Anexar" button into each alert card
  document.querySelectorAll('.alert-actions').forEach((actionsDiv, idx) => {
    const alertCard = actionsDiv.closest('[id^="alert-card-"]');
    if (!alertCard) return;
    const alertId = alertCard.id.replace('alert-card-', '');
    const titleEl = alertCard.querySelector('.alert-title');
    const title   = titleEl ? titleEl.textContent.trim() : 'Alerta';
    if (!actionsDiv.querySelector('.attach-btn')) {
      const btn = document.createElement('button');
      btn.className = 'btn-ghost btn-sm attach-btn';
      btn.textContent = '📎 Anexar';
      btn.onclick = () => openAttachModal(alertId, title);
      actionsDiv.appendChild(btn);
    }
  });
}
