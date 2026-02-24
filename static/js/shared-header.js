/**
 * shared-header.js
 * Injeta o cabeçalho de navegação em todas as sub-páginas.
 * Não executa na raiz (/) pois o index.html já tem seu próprio header.
 */
(function () {
  'use strict';

  // Não injeta na página principal (ela já tem o header no HTML)
  if (window.location.pathname === '/' || window.location.pathname === '/index.html') return;

  /* ── Detecta página atual para highlight ─────────────────── */
  const path = window.location.pathname;
  function isActive(href) {
    return path.endsWith(href.replace(/^\/pages\//, '')) || path === href;
  }
  function activeClass(href) {
    return isActive(href) ? ' style="background:var(--blue-light,rgba(37,99,235,.1));color:var(--blue,#2563eb);border-radius:8px;"' : '';
  }

  /* ── Tema ────────────────────────────────────────────────── */
  const isDespesaPage = path.includes('/pages/despesa');

  function initTheme() {
    // Despesa pages are always dark (their own CSS vars require dark background)
    const saved = isDespesaPage ? 'dark' : localStorage.getItem('theme');
    if (saved === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }
  function toggleTheme() {
    if (isDespesaPage) return; // theme locked on despesa pages
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    }
    syncThemeBtn();
  }
  function syncThemeBtn() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    document.querySelectorAll('.shd-theme-label').forEach(el => {
      el.textContent = isDark ? 'Tema Claro' : 'Tema Escuro';
    });
  }
  initTheme();

  /* ── HTML do header ──────────────────────────────────────── */
  const NAV_ITEMS = {
    documentos: [
      { href: '/pages/rpa.html',             name: 'RPA',                    desc: 'Recibo de Pagamento Autônomo' },
      { href: '/pages/pdf.html',             name: 'Editor de PDF',          desc: 'Mesclar, dividir e proteger' },
      { href: '/pages/gerador-empenho.html', name: 'Texto de Empenho',      desc: 'Gerar descrição de empenho com IA' },
      { href: '/pages/visualizador.html',    name: 'Rel. de Empenhos',       desc: 'Visualizar e filtrar empenhos' },
      { href: '/pages/auditor.html',         name: 'Auditor de NF',          desc: 'Auditoria de notas fiscais com IA' },
    ],
    financeiro: [
      { href: '/pages/extratos.html',             name: 'Extratos Bancários',      desc: 'Organizar arquivos de extrato' },
      { href: '/pages/tarifas-bancarias.html',    name: 'Analisador Financeiro',   desc: 'Tarifas e encargos bancários' },
      { href: '/pages/fornecimento.html',         name: 'Aquisições',              desc: 'Solicitações de aquisição' },
      { href: '/pages/despesa-prefeitura.html',   name: 'Despesa Pública',         desc: 'Visor de despesas da prefeitura' },
      { href: '/pages/despesa-relatorios.html',   name: 'Relatórios de Despesa',   desc: 'Comparar períodos e histórico' },
    ],
    ferramentas: [
      { href: '/pages/cnpj.html',       name: 'Consulta CNPJ',    desc: 'Consultar dados de empresas' },
      { href: '/pages/renomear.html',   name: 'Renomear com IA',  desc: 'Renomear PDFs e extratos' },
      { href: '/pages/tarefas.html',    name: 'Tarefas Kanban',   desc: 'Gerenciar atividades' },
      { href: '/pages/calendario.html', name: 'Calendário',       desc: 'Calendário de pagamentos' },
    ],
  };

  function buildGroupItems(items) {
    return items.map(item => `
      <a href="${item.href}" class="nav-group-item"${activeClass(item.href)}>
        <div class="nav-group-item-text">
          <span class="nav-group-item-name">${item.name}</span>
          <span class="nav-group-item-desc">${item.desc}</span>
        </div>
      </a>`).join('');
  }

  function buildMobileItems(items) {
    return items.map(item => `
      <a href="${item.href}" class="mobile-nav-item${isActive(item.href) ? ' active' : ''}" style="text-decoration:none;">
        ${item.name}
      </a>`).join('');
  }

  const isDarkNow = document.documentElement.getAttribute('data-theme') === 'dark';
  const themeLabel = isDarkNow ? 'Tema Claro' : 'Tema Escuro';

  const headerHTML = `
<header class="header" id="shd-header">
  <div class="header-inner">
    <div class="header-left">
      <button class="hamburger" id="shd-hamburger">
        <span></span><span></span><span></span>
      </button>
      <div class="header-brand">
        <a href="/" style="display:flex;align-items:center;text-decoration:none;">
          <img src="/static/img/brasao.png" alt="Brasão de Inajá" style="height:48px;width:auto;object-fit:contain;" />
          <div class="header-title" style="margin-left:10px;">
            <h1>Prefeitura de Inajá</h1>
            <p>Gestão Municipal</p>
          </div>
        </a>
      </div>
    </div>

    <nav class="desktop-nav">
      <a href="/" class="nav-tab" style="text-decoration:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
        </svg>
        Credores Fixos
      </a>

      <div class="nav-sep"></div>

      <div class="nav-group">
        <button class="nav-group-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          Documentos
          <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div class="nav-group-menu">
          <div class="nav-group-title">Documentos</div>
          ${buildGroupItems(NAV_ITEMS.documentos)}
        </div>
      </div>

      <div class="nav-group">
        <button class="nav-group-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8v1m0 9v1"/></svg>
          Financeiro
          <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div class="nav-group-menu">
          <div class="nav-group-title">Financeiro</div>
          ${buildGroupItems(NAV_ITEMS.financeiro)}
        </div>
      </div>

      <div class="nav-group">
        <button class="nav-group-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
          Ferramentas
          <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div class="nav-group-menu">
          <div class="nav-group-title">Ferramentas</div>
          ${buildGroupItems(NAV_ITEMS.ferramentas)}
        </div>
      </div>
    </nav>

    <div class="header-right">
      <div class="dropdown">
        <button class="dropdown-toggle" id="shd-dropdown-toggle">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
          </svg>
        </button>
        <div class="dropdown-menu" id="shd-dropdown-menu">
          <button class="dropdown-item theme-toggle" id="shd-theme-toggle">
            <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
            </svg>
            <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
            <span class="theme-label shd-theme-label">${themeLabel}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</header>

<!-- Mobile nav -->
<div class="mobile-nav" id="shd-mobile-nav">
  <div class="mobile-nav-header">
    <span>Menu</span>
    <button class="mobile-nav-close" id="shd-mobile-nav-close">&times;</button>
  </div>
  <a href="/" class="mobile-nav-item" style="text-decoration:none;">Credores Fixos</a>
  <div class="mobile-nav-divider"></div>
  <div class="mobile-nav-label">Documentos</div>
  ${buildMobileItems(NAV_ITEMS.documentos)}
  <div class="mobile-nav-divider"></div>
  <div class="mobile-nav-label">Financeiro</div>
  ${buildMobileItems(NAV_ITEMS.financeiro)}
  <div class="mobile-nav-divider"></div>
  <div class="mobile-nav-label">Ferramentas</div>
  ${buildMobileItems(NAV_ITEMS.ferramentas)}
  <div class="mobile-nav-divider"></div>
  <button class="mobile-nav-item theme-toggle" id="shd-mobile-theme">
    <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;flex-shrink:0;">
      <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
    </svg>
    <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;flex-shrink:0;">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
    <span class="shd-theme-label">${themeLabel}</span>
  </button>
</div>
<div class="mobile-nav-overlay" id="shd-mobile-overlay"></div>`;

  /* ── Injeta + Event listeners após DOM pronto ───────────────*/
  function initDOM() {
    document.body.insertAdjacentHTML('afterbegin', headerHTML);

    // Rodapé em todas as sub-páginas
    if (!document.querySelector('.shd-footer')) {
      document.body.insertAdjacentHTML('beforeend',
        `<footer class="shd-footer" style="text-align:center;padding:14px 0 18px;font-size:12px;color:var(--text-3,#9ca3af);border-top:1px solid var(--border,rgba(0,0,0,.08));margin-top:32px">
          Desenvolvido por <strong style="color:var(--text-2,#6b7280)">Aleksandro Alves</strong>
        </footer>`
      );
    }

    function openMobile() {
      document.getElementById('shd-hamburger').classList.add('active');
      document.getElementById('shd-mobile-nav').classList.add('open');
      document.getElementById('shd-mobile-overlay').classList.add('open');
      document.body.style.overflow = 'hidden';
    }
    function closeMobile() {
      document.getElementById('shd-hamburger').classList.remove('active');
      document.getElementById('shd-mobile-nav').classList.remove('open');
      document.getElementById('shd-mobile-overlay').classList.remove('open');
      document.body.style.overflow = '';
    }

    document.getElementById('shd-hamburger').addEventListener('click', () => {
      document.getElementById('shd-mobile-nav').classList.contains('open') ? closeMobile() : openMobile();
    });
    document.getElementById('shd-mobile-nav-close').addEventListener('click', closeMobile);
    document.getElementById('shd-mobile-overlay').addEventListener('click', closeMobile);

    // Nav group dropdowns
    document.querySelectorAll('#shd-header .nav-group-btn').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const group = btn.closest('.nav-group');
        const isOpen = group.classList.contains('open');
        document.querySelectorAll('#shd-header .nav-group').forEach(g => g.classList.remove('open'));
        if (!isOpen) group.classList.add('open');
      });
    });
    document.querySelectorAll('#shd-header .nav-group-menu').forEach(menu => {
      menu.addEventListener('click', e => {
        if (e.target.tagName !== 'A' && !e.target.closest('a')) e.stopPropagation();
      });
    });

    // Dropdown (3 dots)
    const ddToggle = document.getElementById('shd-dropdown-toggle');
    const ddParent = ddToggle.parentElement;
    ddToggle.addEventListener('click', e => {
      e.stopPropagation();
      ddParent.classList.toggle('open');
    });

    // Close all on outside click
    document.addEventListener('click', () => {
      document.querySelectorAll('#shd-header .nav-group').forEach(g => g.classList.remove('open'));
      ddParent.classList.remove('open');
    });

    // Theme toggle (desktop + mobile)
    document.getElementById('shd-theme-toggle').addEventListener('click', () => {
      ddParent.classList.remove('open');
      toggleTheme();
    });
    document.getElementById('shd-mobile-theme').addEventListener('click', () => {
      closeMobile();
      toggleTheme();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDOM);
  } else {
    initDOM();
  }

})();
