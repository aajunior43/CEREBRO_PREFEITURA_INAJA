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
    } else if (saved === 'vintage') {
      document.documentElement.setAttribute('data-theme', 'vintage');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }
  function toggleTheme() {
    if (isDespesaPage) return; // theme locked on despesa pages
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    if (current === 'light') {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else if (current === 'dark') {
      document.documentElement.setAttribute('data-theme', 'vintage');
      localStorage.setItem('theme', 'vintage');
    } else {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
    }
    syncThemeBtn();
  }
  function syncThemeBtn() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    let text = 'Tema Escuro';
    if (current === 'dark') text = 'Tema Vintage';
    if (current === 'vintage') text = 'Tema Claro';
    document.querySelectorAll('.shd-theme-label').forEach(el => {
      el.textContent = text;
    });
  }
  initTheme();

  /* ── HTML do header ──────────────────────────────────────── */
  const NAV_ITEMS = {
    documentos: [
      { href: '/pages/documentos.html',      name: 'Centro de Documentos',   desc: 'Salvar e organizar arquivos' },
      { href: '/pages/rpa.html',             name: 'RPA',                    desc: 'Recibo de Pagamento Autônomo' },
      { href: '/pages/pdf.html',             name: 'Editor de PDF',          desc: 'Mesclar, dividir e proteger' },
      { href: '/pages/gerador-empenho.html', name: 'Texto de Empenho',      desc: 'Gerar descrição de empenho com IA' },
      { href: '/pages/visualizador.html',    name: 'Rel. de Empenhos',       desc: 'Visualizar e filtrar empenhos' },
      { href: '/pages/auditor.html',         name: 'Auditor de NF',          desc: 'Auditoria de notas fiscais com IA' },
      { href: '/pages/prazos.html',          name: 'Prazos',                 desc: 'Contratos e prazos críticos' },
      { href: '/pages/protocolo.html',       name: 'Protocolo',              desc: 'Ofícios, memorandos e documentos' },
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
      { href: '/pages/manual.html',     name: '📖 Manual',        desc: 'Guia completo do sistema' },
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
        Credores
      </a>
      <a href="/pages/extratos.html" class="nav-tab" style="text-decoration:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
        Extratos
      </a>
      <a href="/pages/tarefas.html" class="nav-tab" style="text-decoration:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
        Tarefas
      </a>
      <div class="nav-group">
        <button class="nav-group-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          Módulos
          <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div class="nav-group-menu">
          <div class="nav-group-title">Documentos</div>
          ${buildGroupItems(NAV_ITEMS.documentos)}
          <div class="nav-group-title">Financeiro</div>
          ${buildGroupItems(NAV_ITEMS.financeiro)}
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
  <a href="/pages/extratos.html" class="mobile-nav-item${isActive('/pages/extratos.html') ? ' active' : ''}" style="text-decoration:none;">Extratos</a>
  <a href="/pages/tarefas.html" class="mobile-nav-item${isActive('/pages/tarefas.html') ? ' active' : ''}" style="text-decoration:none;">Tarefas</a>
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

    /* ── Breadcrumb ──────────────────────────────────────────── */
    const allPages = [
      ...NAV_ITEMS.documentos.map(i => ({...i, cat: 'Documentos'})),
      ...NAV_ITEMS.financeiro.map(i => ({...i, cat: 'Financeiro'})),
      ...NAV_ITEMS.ferramentas.map(i => ({...i, cat: 'Ferramentas'})),
    ];
    const currentPage = allPages.find(p => isActive(p.href));
    if (currentPage) {
      const crumb = document.createElement('div');
      crumb.className = 'shd-breadcrumb';
      crumb.innerHTML = `
        <a href="/" class="shd-bc-link">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
          Início
        </a>
        <span class="shd-bc-sep">›</span>
        <span class="shd-bc-cat">${currentPage.cat}</span>
        <span class="shd-bc-sep">›</span>
        <span class="shd-bc-current">${currentPage.name.replace('📖 ', '')}</span>`;
      const firstMainEl = document.body.querySelector('main, .page-wrap, section, .content') || document.body.children[1];
      if (firstMainEl) {
        document.body.insertBefore(crumb, firstMainEl);
      } else {
        document.body.querySelector('#shd-header')?.insertAdjacentElement('afterend', crumb);
      }
    }

    /* ── Bottom nav em sub-páginas ───────────────────────────── */
    if (!document.getElementById('shd-bottom-nav')) {
      const bnav = document.createElement('nav');
      bnav.className = 'bottom-nav';
      bnav.id = 'shd-bottom-nav';
      bnav.setAttribute('aria-label', 'Navegação mobile');
      bnav.innerHTML = `
        <div class="bottom-nav-items">
          <a class="bottom-nav-item" href="/">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
            <span>Credores</span>
            <span class="bottom-nav-indicator"></span>
          </a>
          <a class="bottom-nav-item${isActive('/pages/extratos.html')?' active':''}" href="/pages/extratos.html">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
            <span>Extratos</span>
            <span class="bottom-nav-indicator"></span>
          </a>
          <a class="bottom-nav-item${isActive('/pages/tarefas.html')?' active':''}" href="/pages/tarefas.html">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
            <span>Tarefas</span>
            <span class="bottom-nav-indicator"></span>
          </a>
          <a class="bottom-nav-item${isActive('/pages/cnpj.html')?' active':''}" href="/pages/cnpj.html">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>
            <span>CNPJ</span>
            <span class="bottom-nav-indicator"></span>
          </a>
          <button class="bottom-nav-item" id="shd-bnav-menu">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            <span>Menu</span>
            <span class="bottom-nav-indicator"></span>
          </button>
        </div>`;
      document.body.appendChild(bnav);
      document.getElementById('shd-bnav-menu')?.addEventListener('click', () => {
        const mobile = document.getElementById('shd-mobile-nav');
        if (!mobile) return;
        mobile.classList.contains('open') ? closeMobile() : openMobile();
      });
    }

    /* ── Breadcrumb CSS (injeta uma vez) ─────────────────────── */
    if (!document.getElementById('shd-breadcrumb-style')) {
      const s = document.createElement('style');
      s.id = 'shd-breadcrumb-style';
      s.textContent = `
        .shd-breadcrumb {
          display: flex; align-items: center; gap: 6px;
          padding: 8px 28px; font-size: 12px; font-weight: 500;
          color: var(--text-3); background: var(--bg);
          border-bottom: 1px solid var(--border);
        }
        .shd-bc-link {
          display: inline-flex; align-items: center; gap: 4px;
          color: var(--text-3); text-decoration: none;
          transition: color 0.15s;
        }
        .shd-bc-link:hover { color: var(--blue); }
        .shd-bc-sep { color: var(--text-3); opacity: 0.5; }
        .shd-bc-cat { color: var(--text-3); }
        .shd-bc-current { color: var(--text-2); font-weight: 600; }
        @media (max-width: 600px) {
          .shd-breadcrumb { padding: 6px 16px; font-size: 11px; }
          body { padding-bottom: 64px; }
        }
      `;
      document.head.appendChild(s);
    }

    // Rodapé em todas as sub-páginas
    if (!document.querySelector('.shd-footer')) {
      document.body.insertAdjacentHTML('beforeend',
        `<footer class="shd-footer" style="text-align:center;padding:14px 0 18px;font-size:12px;color:var(--text-3,#9ca3af);border-top:1px solid var(--border,rgba(0,0,0,.08));margin-top:32px">
          Desenvolvido por <strong style="color:var(--text-2,#6b7280)">Aleksandro Alves</strong>
        </footer>`
      );
    }

    // Tooltip system
    if (!document.getElementById('shd-tooltip-style')) {
      const style = document.createElement('style');
      style.id = 'shd-tooltip-style';
      style.textContent = `
        [data-tooltip] { position: relative; }
        [data-tooltip]::after {
          content: attr(data-tooltip);
          position: absolute;
          bottom: calc(100% + 8px);
          left: 50%;
          transform: translateX(-50%);
          background: #1e2a38;
          color: #fff;
          padding: 6px 10px;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 500;
          white-space: nowrap;
          max-width: 220px;
          white-space: pre-wrap;
          text-align: center;
          pointer-events: none;
          opacity: 0;
          transition: opacity .15s;
          z-index: 9999;
          box-shadow: 0 2px 8px rgba(0,0,0,.25);
        }
        [data-tooltip]::before {
          content: '';
          position: absolute;
          bottom: calc(100% + 2px);
          left: 50%;
          transform: translateX(-50%);
          border: 5px solid transparent;
          border-top-color: #1e2a38;
          pointer-events: none;
          opacity: 0;
          transition: opacity .15s;
          z-index: 9999;
        }
        [data-tooltip]:hover::after,
        [data-tooltip]:hover::before { opacity: 1; }
        [data-theme="dark"] [data-tooltip]::after { background: #e2e8f0; color: #1e2a38; box-shadow: 0 2px 8px rgba(0,0,0,.5); }
        [data-theme="dark"] [data-tooltip]::before { border-top-color: #e2e8f0; }
      `;
      document.head.appendChild(style);
    }

    // Sincroniza chaves do banco → localStorage (garante que módulos de IA funcionem mesmo após limpeza de cache)
    if (!localStorage.getItem('api_openrouter_key')) {
      fetch('/api/config').then(r => r.json()).then(cfg => {
        if (cfg.api_openrouter_key)    { localStorage.setItem('api_openrouter_key',    cfg.api_openrouter_key);    localStorage.setItem('ext_ia_key',    cfg.api_openrouter_key); }
        if (cfg.api_openrouter_modelo) { localStorage.setItem('api_openrouter_modelo', cfg.api_openrouter_modelo); localStorage.setItem('ext_ia_modelo', cfg.api_openrouter_modelo); }
        if (cfg.api_cnpja_key)         { localStorage.setItem('api_cnpja_key',          cfg.api_cnpja_key); }
      }).catch(() => {});
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

    document.getElementById('shd-hamburger')?.addEventListener('click', () => {
      const mobile = document.getElementById('shd-mobile-nav');
      if (!mobile) return;
      mobile.classList.contains('open') ? closeMobile() : openMobile();
    });
    document.getElementById('shd-mobile-nav-close')?.addEventListener('click', closeMobile);
    document.getElementById('shd-mobile-overlay')?.addEventListener('click', closeMobile);

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
    const ddParent = ddToggle?.parentElement;
    ddToggle?.addEventListener('click', e => {
      e.stopPropagation();
      ddParent?.classList.toggle('open');
    });

    // Close all on outside click
    document.addEventListener('click', () => {
      document.querySelectorAll('#shd-header .nav-group').forEach(g => g.classList.remove('open'));
      ddParent?.classList.remove('open');
    });

    // Theme toggle (desktop + mobile)
    document.getElementById('shd-theme-toggle')?.addEventListener('click', () => {
      ddParent?.classList.remove('open');
      toggleTheme();
    });
    document.getElementById('shd-mobile-theme')?.addEventListener('click', () => {
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
