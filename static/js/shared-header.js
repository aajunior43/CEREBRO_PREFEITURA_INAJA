/**
 * shared-header.js
 * Injeta o cabeçalho de navegação em todas as sub-páginas.
 * Não executa na raiz (/) pois o index.html já tem seu próprio header.
 */
(function () {
  'use strict';

  // Não injeta se a página principal (index.html) já possuir o header embutido
  if (document.body && document.body.classList.contains('home-page')) return;

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
  function toggleTheme() {
    if (isDespesaPage) return; // theme locked on despesa pages
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    if (current === 'light') {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else if (current === 'dark') {
      document.documentElement.setAttribute('data-theme', 'vintage');
      localStorage.setItem('theme', 'vintage');
    } else if (current === 'vintage') {
      document.documentElement.setAttribute('data-theme', 'cosmos');
      localStorage.setItem('theme', 'cosmos');
    } else if (current === 'cosmos') {
      document.documentElement.setAttribute('data-theme', 'esmeralda');
      localStorage.setItem('theme', 'esmeralda');
    } else if (current === 'esmeralda') {
      document.documentElement.setAttribute('data-theme', 'diamante');
      localStorage.setItem('theme', 'diamante');
    } else if (current === 'diamante') {
      document.documentElement.setAttribute('data-theme', 'safira');
      localStorage.setItem('theme', 'safira');
    } else if (current === 'safira') {
      document.documentElement.setAttribute('data-theme', 'vulcano');
      localStorage.setItem('theme', 'vulcano');
    } else if (current === 'vulcano') {
      document.documentElement.setAttribute('data-theme', 'crepusculo');
      localStorage.setItem('theme', 'crepusculo');
    } else if (current === 'crepusculo') {
      document.documentElement.setAttribute('data-theme', 'nordico');
      localStorage.setItem('theme', 'nordico');
    } else if (current === 'nordico') {
      document.documentElement.setAttribute('data-theme', 'cacau');
      localStorage.setItem('theme', 'cacau');
    } else if (current === 'cacau') {
      document.documentElement.setAttribute('data-theme', 'ametista');
      localStorage.setItem('theme', 'ametista');
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
    document.querySelectorAll('.shd-theme-label').forEach(el => {
      el.textContent = text;
    });
  }

  function initCosmosEffects() {
    if (window.__cosmosEffectsInitialized) return;
    window.__cosmosEffectsInitialized = true;

    const cosmosState = {
      timer: null,
    };

    function isCosmosTheme() {
      return document.documentElement.getAttribute('data-theme') === 'cosmos';
    }

    function prefersReducedMotion() {
      return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function clearTimer() {
      if (cosmosState.timer) {
        clearTimeout(cosmosState.timer);
        cosmosState.timer = null;
      }
    }

    function createComet() {
      if (!isCosmosTheme() || prefersReducedMotion() || document.hidden || !document.body) return;

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
      cosmosState.timer = window.setTimeout(() => {
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

    new MutationObserver(syncCosmosEffects).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) clearTimer();
      else syncCosmosEffects();
    });

    syncCosmosEffects();
  }
  initTheme();

  /* ── HTML do header ──────────────────────────────────────── */
  const NAV_ITEMS = {
    documentos: [
      { href: '/pages/documentos.html',      name: 'Centro de Documentos',   desc: 'Salvar e organizar arquivos' },
      { href: '/pages/mural.html',           name: 'Mural Interativo',       desc: 'Avisos e tarefas compartilhadas' },
      { href: '/pages/rpa.html',             name: 'Gerador de RPAs',        desc: 'Recibo de Pagamento Autônomo' },
      { href: '/pages/pdf.html',             name: 'Editor de PDF',          desc: 'Mesclar, dividir e proteger' },
      { href: '/pages/latex-pdf.html',       name: 'Gerador PDF LaTeX',      desc: 'Criar documentos com IA' },
      { href: '/pages/assistente-empenho.html', name: 'Gerador de Descrição para Empenhos', desc: 'Gerar descrição de empenho com IA' },
      { href: '/pages/classificador-despesa.html', name: 'Classificador de Despesas', desc: 'Identificar desdobramento correto da despesa (TCE-PR)' },
      { href: '/pages/visualizador.html',    name: 'Relação de Empenhos Emitidos',  desc: 'Visualizar e filtrar empenhos' },
      { href: '/pages/auditor.html',         name: 'Auditor de NF',          desc: 'Auditoria de notas fiscais com IA' },
      { href: '/pages/protocolo.html',       name: 'Protocolo',              desc: 'Ofícios, memorandos e documentos' },
      { href: '/pages/autentique-assinatura.html', name: 'Assinatura Digital', desc: 'Enviar documento para assinatura' },
    ],
    financeiro: [

      { href: '/pages/fornecimento.html',         name: 'Gerador de Solicitação de Compra ou Serviço',    desc: 'Pedidos e fluxo de compras' },
      { href: '/pages/despesa-prefeitura.html',   name: 'Dotação Orçamentária',        desc: 'Consulta de despesas e dotações' },
      { href: '/pages/despesa-relatorios.html',   name: 'Comparativo Orçamentário',     desc: 'Comparar períodos e histórico' },
    ],
    ferramentas: [
      { href: '/pages/cnpj.html',       name: 'Consulta de CNPJ',       desc: 'Consultar dados de empresas' },

      { href: '/pages/calculadora-diarias.html', name: 'Calculadora de Diárias', desc: 'Calcular diárias de viagens' },

      { href: '/pages/calendario.html', name: 'Calendário', desc: 'Calendário de pagamentos' },
      { href: '/pages/manual.html',     name: 'Manual do Sistema',      desc: 'Guia completo do sistema' },
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
          </div>
        </a>
      </div>
    </div>

    <nav class="desktop-nav">
      <a href="/index.html" class="nav-tab" style="text-decoration:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <line x1="9" y1="3" x2="9" y2="21"/>
          <line x1="13" y1="9" x2="19" y2="9"/>
          <line x1="13" y1="13" x2="19" y2="13"/>
        </svg>
        Painel Financeiro
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
          <div class="theme-selector-group" style="padding: 10px 14px 6px; border-top: 1px solid var(--border); margin-top: 4px;">
            <div style="font-size: 10px; font-weight: 800; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">🎨 Aparência</div>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px;">
              <button type="button" class="theme-select-btn" data-theme-val="light">☀️ Claro</button>
              <button type="button" class="theme-select-btn" data-theme-val="dark">🌙 Escuro</button>
              <button type="button" class="theme-select-btn" data-theme-val="vintage">🍂 Vintage</button>
              <button type="button" class="theme-select-btn" data-theme-val="cosmos">🌌 Cosmos</button>
              <button type="button" class="theme-select-btn" data-theme-val="esmeralda">💚 Esmeralda</button>
              <button type="button" class="theme-select-btn" data-theme-val="diamante">💎 Diamante</button>
              <button type="button" class="theme-select-btn" data-theme-val="safira">💙 Safira</button>
              <button type="button" class="theme-select-btn" data-theme-val="vulcano">🌋 Vulcano</button>
              <button type="button" class="theme-select-btn" data-theme-val="crepusculo">🌅 Crepúsculo</button>
              <button type="button" class="theme-select-btn" data-theme-val="nordico">❄️ Nórdico</button>
              <button type="button" class="theme-select-btn" data-theme-val="cacau">☕ Cacau</button>
              <button type="button" class="theme-select-btn" data-theme-val="ametista">🔮 Ametista</button>
            </div>
          </div>
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
  <a href="/index.html" class="mobile-nav-item" style="text-decoration:none;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:20px;height:20px;flex-shrink:0;margin-right:8px;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="13" y1="9" x2="19" y2="9"/><line x1="13" y1="13" x2="19" y2="13"/></svg> Painel Financeiro</a>

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
  <div class="theme-selector-group" style="padding: 10px 16px; border-top: 1px solid var(--border); margin-top: 8px;">
    <div style="font-size: 10px; font-weight: 800; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;">🎨 Aparência</div>
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px;">
      <button type="button" class="theme-select-btn" data-theme-val="light">☀️ Claro</button>
      <button type="button" class="theme-select-btn" data-theme-val="dark">🌙 Escuro</button>
      <button type="button" class="theme-select-btn" data-theme-val="vintage">🍂 Vintage</button>
      <button type="button" class="theme-select-btn" data-theme-val="cosmos">🌌 Cosmos</button>
      <button type="button" class="theme-select-btn" data-theme-val="esmeralda">💚 Esmeralda</button>
      <button type="button" class="theme-select-btn" data-theme-val="diamante">💎 Diamante</button>
      <button type="button" class="theme-select-btn" data-theme-val="safira">💙 Safira</button>
      <button type="button" class="theme-select-btn" data-theme-val="vulcano">🌋 Vulcano</button>
      <button type="button" class="theme-select-btn" data-theme-val="crepusculo">🌅 Crepúsculo</button>
      <button type="button" class="theme-select-btn" data-theme-val="nordico">❄️ Nórdico</button>
      <button type="button" class="theme-select-btn" data-theme-val="cacau">☕ Cacau</button>
      <button type="button" class="theme-select-btn" data-theme-val="ametista">🔮 Ametista</button>
    </div>
  </div>
</div>
<div class="mobile-nav-overlay" id="shd-mobile-overlay"></div>`;

  /* ── Injeta + Event listeners após DOM pronto ───────────────*/
  function initDOM() {
    initCosmosEffects();
    document.body.insertAdjacentHTML('afterbegin', headerHTML);

    // Global dynamic glow tracking for buttons and cards on subpages
    document.addEventListener('mousemove', (e) => {
      const el = e.target.closest('[data-glow-btn], .hs-card, .nav-group-item');
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      el.style.setProperty('--glow-x', `${x}px`);
      el.style.setProperty('--glow-y', `${y}px`);
    });

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
      const headerEl = document.body.querySelector('#shd-header');
      const firstMainEl = document.body.querySelector('main, .page-wrap, section, .content');
      if (headerEl) {
        headerEl.insertAdjacentElement('afterend', crumb);
      } else if (firstMainEl && firstMainEl.parentNode === document.body) {
        document.body.insertBefore(crumb, firstMainEl);
      } else {
        document.body.appendChild(crumb);
      }
    }

    /* ── Bottom nav em sub-páginas ───────────────────────────── */
    if (!document.getElementById('shd-bottom-nav')) {
      const bnav = document.createElement('div');
      bnav.id = 'shd-bottom-nav';
      bnav.className = 'bottom-nav';
      bnav.innerHTML = `
        <div class="bottom-nav-items">
          <a class="bottom-nav-item${isActive('/index.html') ? ' active':''}" href="/index.html">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>
            <span>Painel</span>
            <span class="bottom-nav-indicator"></span>
          </a>

          <a class="bottom-nav-item${isActive('/pages/cnpj.html') ? ' active':''}" href="/pages/cnpj.html">
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
        const model = cfg.api_openrouter_modelo || '';
        const iaKey = model.startsWith('opencode-go/') ? (cfg.api_opencode_go_key || cfg.api_openrouter_key) : cfg.api_openrouter_key;
        if (iaKey)                     { localStorage.setItem('api_openrouter_key',    iaKey);                    localStorage.setItem('ext_ia_key',    iaKey); }
        if (cfg.api_openrouter_modelo) { localStorage.setItem('api_openrouter_modelo', cfg.api_openrouter_modelo); localStorage.setItem('ext_ia_modelo', cfg.api_openrouter_modelo); }
        if (cfg.api_cnpja_key)         { localStorage.setItem('api_cnpja_key',          cfg.api_cnpja_key); }
      }).catch(() => {});
    }

    const IA_PAGE_CONFIG = {
      '/pages/protocolo.html': {
        title: 'IA de Protocolo',
        subtitle: 'Assistente para ofícios, memorandos e acompanhamento documental',
        chatPlaceholder: 'Ex: Quais protocolos vencem primeiro ou merecem resposta urgente?',
        emptyMessage: 'Cadastre ou carregue protocolos antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume os protocolos, status e gargalos.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Mostra o que deve ser respondido primeiro.' },
          { id: 'prazos', label: 'Prazos', description: 'Aponta vencimentos, atrasos e riscos.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre os protocolos.' }
        ],
        shortcuts: [
          { label: 'Resumo geral', action: 'analisar' },
          { label: 'Pendências urgentes', action: 'prioridades' },
          { label: 'Prazos críticos', action: 'prazos' }
        ],
        contextBuilder() {
          const rows = Array.from(document.querySelectorAll('.pr-item')).slice(0, 20).map((item) => ({
            numero: item.querySelector('.pr-item-num')?.textContent?.trim() || '',
            assunto: item.querySelector('.pr-item-title')?.textContent?.trim() || '',
            meta: item.querySelector('.pr-item-meta')?.textContent?.replace(/\s+/g, ' ')?.trim() || '',
            obs: item.querySelector('.pr-item-desc')?.textContent?.trim() || ''
          }));
          return { page: 'protocolo', protocolos_visiveis: rows };
        }
      },
      '/pages/documentos.html': {
        title: 'IA de Documentos',
        subtitle: 'Assistente para organização documental e critérios de arquivamento',
        chatPlaceholder: 'Ex: Como organizar melhor esses documentos por categoria?',
        emptyMessage: 'Carregue documentos antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume o acervo visível e sugere organização.' },
          { id: 'categorizar', label: 'Categorias', description: 'Sugere grupos, padrões e separações úteis.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Mostra o que merece revisão ou ação primeiro.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre os documentos.' }
        ],
        shortcuts: [
          { label: 'Resumo do acervo', action: 'analisar' },
          { label: 'Sugerir categorias', action: 'categorizar' },
          { label: 'O que revisar primeiro', action: 'prioridades' }
        ]
      },
      '/pages/fornecimento.html': {
        title: 'IA de Aquisições',
        subtitle: 'Assistente para pedidos, fornecedores e fluxo de compras',
        chatPlaceholder: 'Ex: O que está pendente no fluxo de aquisição?',
        emptyMessage: 'Cadastre ou carregue dados de aquisição antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume o quadro de aquisições e etapas atuais.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Aponta o que acelerar no processo.' },
          { id: 'riscos', label: 'Riscos', description: 'Sinaliza atrasos, gargalos e dependências.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre as aquisições.' }
        ],
        shortcuts: [
          { label: 'Resumo das aquisições', action: 'analisar' },
          { label: 'Próximas ações', action: 'prioridades' },
          { label: 'Riscos do processo', action: 'riscos' }
        ]
      },
      '/pages/cnpj.html': {
        title: 'IA de CNPJ',
        subtitle: 'Assistente para leitura de cadastro empresarial e checagens rápidas',
        chatPlaceholder: 'Ex: O que devo conferir primeiro neste CNPJ?',
        emptyMessage: 'Consulte um CNPJ antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume os dados consultados e os pontos principais.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Mostra o que vale conferir primeiro no cadastro.' },
          { id: 'riscos', label: 'Riscos', description: 'Aponta inconsistências ou alertas cadastrais.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre o cadastro exibido.' }
        ],
        shortcuts: [
          { label: 'Resumo do cadastro', action: 'analisar' },
          { label: 'O que conferir', action: 'prioridades' },
          { label: 'Alertas cadastrais', action: 'riscos' }
        ]
      },
      '/pages/pdf.html': {
        title: 'IA de PDF',
        subtitle: 'Assistente para orientar fusão, divisão, proteção e organização de arquivos',
        chatPlaceholder: 'Ex: Qual a melhor forma de organizar estes PDFs?',
        emptyMessage: 'Carregue arquivos PDF antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume o cenário atual e sugere organização dos arquivos.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Indica a ordem mais eficiente para trabalhar os PDFs.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre o fluxo com PDFs.' }
        ],
        shortcuts: [
          { label: 'Sugestão de fluxo', action: 'analisar' },
          { label: 'O que fazer primeiro', action: 'prioridades' }
        ]
      },
      '/pages/rpa.html': {
        title: 'IA de RPA',
        subtitle: 'Assistente para conferência e preenchimento de recibos',
        chatPlaceholder: 'Ex: Quais campos do RPA preciso revisar com mais atenção?',
        emptyMessage: 'Preencha ou carregue dados do RPA antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume o RPA e sugere conferências.' },
          { id: 'riscos', label: 'Riscos', description: 'Aponta campos sensíveis, ausências e riscos de erro.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre o RPA atual.' }
        ],
        shortcuts: [
          { label: 'Resumo do RPA', action: 'analisar' },
          { label: 'Campos críticos', action: 'riscos' }
        ]
      },
      '/pages/manual.html': {
        title: 'IA do Manual',
        subtitle: 'Assistente para orientar o uso do sistema e localizar instruções',
        chatPlaceholder: 'Ex: Onde encontro a orientação para usar este módulo?',
        emptyMessage: 'Abra o manual para usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume o conteúdo visível do manual.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Aponta os trechos mais úteis para começar.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre o manual.' }
        ],
        shortcuts: [
          { label: 'Resumo desta seção', action: 'analisar' },
          { label: 'Onde começar', action: 'prioridades' }
        ]
      },
      '/pages/visualizador.html': {
        title: 'IA de Empenhos',
        subtitle: 'Assistente para leitura, filtros e interpretação de empenhos',
        chatPlaceholder: 'Ex: Quais empenhos merecem atenção imediata?',
        emptyMessage: 'Carregue dados de empenhos antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume os empenhos visíveis e os principais achados.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Mostra o que merece análise primeiro.' },
          { id: 'riscos', label: 'Riscos', description: 'Aponta padrões estranhos, valores sensíveis e gaps.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre os empenhos.' }
        ],
        shortcuts: [
          { label: 'Resumo dos empenhos', action: 'analisar' },
          { label: 'O que priorizar', action: 'prioridades' },
          { label: 'Riscos detectados', action: 'riscos' }
        ]
      },
      '/pages/calendario.html': {
        title: 'IA do Calendário',
        subtitle: 'Assistente para organização de eventos, pagamentos e compromissos',
        chatPlaceholder: 'Ex: Quais eventos desta agenda são mais urgentes?',
        emptyMessage: 'Cadastre ou carregue eventos antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume os compromissos e a agenda atual.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Mostra o que merece atenção imediata.' },
          { id: 'prazos', label: 'Prazos', description: 'Aponta vencimentos, datas críticas e marcos próximos.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre a agenda.' }
        ],
        shortcuts: [
          { label: 'Resumo da agenda', action: 'analisar' },
          { label: 'Compromissos urgentes', action: 'prioridades' },
          { label: 'Datas críticas', action: 'prazos' }
        ]
      },
      '/pages/calculadora-diarias.html': {
        title: 'IA de Diárias',
        subtitle: 'Assistente para cálculo, revisão e conferência de diárias',
        chatPlaceholder: 'Ex: O que preciso conferir antes de finalizar esta diária?',
        emptyMessage: 'Preencha os dados da diária antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume o cálculo atual e os parâmetros informados.' },
          { id: 'riscos', label: 'Riscos', description: 'Aponta inconsistências e campos que exigem revisão.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre o cálculo da diária.' }
        ],
        shortcuts: [
          { label: 'Resumo do cálculo', action: 'analisar' },
          { label: 'O que revisar', action: 'riscos' }
        ]
      },
      '/pages/autentique-assinatura.html': {
        title: 'IA de Assinatura Digital',
        subtitle: 'Assistente para conferência de envios, signatários e pendências',
        chatPlaceholder: 'Ex: Quais documentos de assinatura merecem acompanhamento?',
        emptyMessage: 'Carregue os envios de assinatura antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume os envios e o estágio das assinaturas.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Mostra o que deve ser acompanhado primeiro.' },
          { id: 'riscos', label: 'Riscos', description: 'Aponta travas, pendências e documentos sensíveis.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre as assinaturas.' }
        ],
        shortcuts: [
          { label: 'Resumo dos envios', action: 'analisar' },
          { label: 'Pendências prioritárias', action: 'prioridades' },
          { label: 'Riscos do fluxo', action: 'riscos' }
        ]
      },
      '/pages/auditor.html': {
        title: 'IA de Auditoria',
        subtitle: 'Assistente para leitura de NF, inconsistências e validação',
        chatPlaceholder: 'Ex: Quais inconsistências devo revisar nesta auditoria?',
        emptyMessage: 'Carregue uma nota fiscal antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume a auditoria atual e os principais achados.' },
          { id: 'riscos', label: 'Riscos', description: 'Aponta inconsistências, alertas e sinais de problema.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Mostra o que deve ser conferido primeiro.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre a auditoria.' }
        ],
        shortcuts: [
          { label: 'Resumo da auditoria', action: 'analisar' },
          { label: 'Riscos detectados', action: 'riscos' },
          { label: 'Itens prioritários', action: 'prioridades' }
        ]
      },
      '/pages/assistente-empenho.html': {
        title: 'IA de Empenho',
        subtitle: 'Assistente para compor e revisar descrições de empenho',
        chatPlaceholder: 'Ex: Como deixar esta descrição de empenho mais técnica?',
        emptyMessage: 'Informe os dados do empenho antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume a composição atual do empenho.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Aponta lacunas e melhorias mais importantes.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre o empenho.' }
        ],
        shortcuts: [
          { label: 'Resumo do empenho', action: 'analisar' },
          { label: 'Melhorias principais', action: 'prioridades' }
        ]
      },
      '/pages/extratos.html': {
        title: 'IA de Extratos',
        subtitle: 'Assistente para leitura e organização de extratos importados',
        chatPlaceholder: 'Ex: Que padrão importante existe neste extrato?',
        emptyMessage: 'Carregue extratos antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume os extratos e os principais padrões visíveis.' },
          { id: 'riscos', label: 'Riscos', description: 'Aponta anomalias, cobranças e movimentações relevantes.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre os extratos.' }
        ],
        shortcuts: [
          { label: 'Resumo do extrato', action: 'analisar' },
          { label: 'Possíveis anomalias', action: 'riscos' }
        ]
      },
      '/pages/gerador-empenho.html': {
        title: 'IA do Gerador de Empenho',
        subtitle: 'Assistente para revisar entradas e orientar a geração do texto',
        chatPlaceholder: 'Ex: Como melhorar o texto gerado para este empenho?',
        emptyMessage: 'Carregue um documento ou informe um texto antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume a entrada atual e orienta a geração.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Aponta o que precisa ajuste antes de gerar.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre a geração do empenho.' }
        ],
        shortcuts: [
          { label: 'Resumo da entrada', action: 'analisar' },
          { label: 'O que ajustar', action: 'prioridades' }
        ]
      },
      '/pages/renomear.html': {
        title: 'IA do Renomeador',
        subtitle: 'Assistente para padronização e estratégia de nomes de arquivos',
        chatPlaceholder: 'Ex: Como padronizar melhor esses nomes?',
        emptyMessage: 'Carregue arquivos antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume o lote atual e sugere padrões de nomenclatura.' },
          { id: 'categorizar', label: 'Categorias', description: 'Sugere separações e critérios para organização.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre la padronização dos nomes.' }
        ],
        shortcuts: [
          { label: 'Padrão sugerido', action: 'analisar' },
          { label: 'Categorias úteis', action: 'categorizar' }
        ]
      },
      '/pages/despesa-prefeitura.html': {
        title: 'IA Orçamentária',
        subtitle: 'Assistente de análise de dotações',
        chatPlaceholder: 'Ex: Qual secretaria tem maior saldo?',
        emptyMessage: 'Carregue um período antes de usar a IA.',
        endpoint: '/api/despesas/ia',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Panorama geral do orçamento, saldos e execução.' },
          { id: 'anomalias', label: 'Anomalias', description: 'Sinaliza baixos saldos, riscos e padrões estranhos.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Aponta onde reforçar recursos ou atenção.' },
          { id: 'cortes', label: 'Cortes', description: 'Sugere onde conter gastos com menor impacto.' },
          { id: 'remanejamento', label: 'Remanejamento', description: 'Simula trocas de saldo entre dotações.' },
          { id: 'relatorio', label: 'Relatório', description: 'Gera resumo técnico para controle interno.' },
          { id: 'chat', label: 'Chat', description: 'Pergunta livre sobre o orçamento carregado.' }
        ],
        shortcuts: [
          { label: 'Resumo executivo', action: 'analisar' },
          { label: 'Riscos imediatos', action: 'anomalias' },
          { label: 'Onde reforçar', action: 'prioridades' },
          { label: 'Onde cortar', action: 'cortes' }
        ],
        contextBuilder() {
          if (typeof window.buildContext === 'function') return window.buildContext();
          return buildGenericIaContext();
        }
      },
      '/pages/despesa-relatorios.html': {
        title: 'IA dos Relatórios',
        subtitle: 'Assistente comparativo de dotações',
        chatPlaceholder: 'Ex: O que piorou do período A para o B?',
        emptyMessage: 'Selecione dois períodos e compare antes de usar a IA.',
        endpoint: '/api/despesas/ia',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Compara os períodos, variações e panorama.' },
          { id: 'anomalias', label: 'Anomalias', description: 'Aponta variações bruscas ou riscos comparativos.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Mostra onde focar a gestão no novo período.' },
          { id: 'relatorio', label: 'Relatório', description: 'Gera análise técnica do comparativo.' },
          { id: 'chat', label: 'Chat', description: 'Pergunta livre sobre a comparação.' }
        ],
        shortcuts: [
          { label: 'Resumo comparativo', action: 'analisar' },
          { label: 'Riscos da comparação', action: 'anomalias' }
        ],
        contextBuilder() {
          if (typeof window.buildComparisonContext === 'function') return window.buildComparisonContext();
          return buildGenericIaContext();
        }
      }
    };

    function ensureIaWidgetScript() {
      return new Promise((resolve) => {
        if (window.IaChatWidget) {
          resolve();
          return;
        }
        const existing = document.querySelector('script[data-ia-chat-widget-script]');
        if (existing) {
          existing.addEventListener('load', () => resolve(), { once: true });
          setTimeout(resolve, 1500);
          return;
        }
        const script = document.createElement('script');
        script.src = '/static/js/ia-chat-widget.js';
        script.async = true;
        script.setAttribute('data-ia-chat-widget-script', 'true');
        script.onload = () => resolve();
        script.onerror = () => resolve();
        document.head.appendChild(script);
      });
    }

    function buildGenericIaContext() {
      const title = document.title || path;
      const heading = document.querySelector('h1, h2')?.textContent?.trim() || '';
      const text = Array.from(document.querySelectorAll('main, section, .content, .page-wrap, .docs-wrap, .pr-wrap, .pz-wrap, .viz-app'))
        .map((el) => el.textContent || '')
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 6000);
      return { page_path: path, page_title: title, page_heading: heading, visible_text: text };
    }

    async function runGenericIaRequest(pageConfig, action, question) {
      const apiKey = localStorage.getItem('api_openrouter_key') || localStorage.getItem('ext_ia_key') || '';
      if (!apiKey && !pageConfig.endpoint) throw new Error('Configure a chave OpenRouter em ADM antes de usar a IA.');
      const model = localStorage.getItem('api_openrouter_modelo') || localStorage.getItem('ext_ia_modelo') || 'opencode-go/deepseek-v4-flash';
      const context = typeof pageConfig.contextBuilder === 'function' ? pageConfig.contextBuilder() : buildGenericIaContext();

      if (pageConfig.endpoint) {
        // Specialized endpoint (like /api/despesas/ia)
        const resp = await fetch(pageConfig.endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, contexto: context, pergunta: question || '' })
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.error?.message || data.error || `Erro HTTP ${resp.status}`);
        return data.resultado || 'Sem resposta da IA.';
      }

      const prompts = {
        analisar: 'Faça uma análise objetiva da aba atual, destacando panorama, achados e pontos que merecem atenção.',
        prioridades: 'Liste as prioridades práticas e a ordem recomendada de atuação na aba atual.',
        riscos: 'Aponte riscos, gargalos, atrasos, inconsistências ou pontos frágeis observáveis na aba atual.',
        prazos: 'Analise prazos, vencimentos, urgências e próximos marcos relevantes da aba atual.',
        categorizar: 'Sugira categorias, agrupamentos e uma organização mais eficiente para os itens da aba atual.',
        chat: question || 'Responda à pergunta do usuário com base no conteúdo atual da aba.'
      };
      const prompt = [
        `Você é um assistente administrativo da Prefeitura de Inajá.`,
        `Aba atual: ${pageConfig.title || document.title || path}`,
        `Objetivo: ${prompts[action] || prompts.analisar}`,
        question && action !== 'chat' ? `Pergunta complementar: ${question}` : '',
        `Contexto da página (JSON):`,
        JSON.stringify(context, null, 2),
        `Responda em português do Brasil, de forma prática, clara e orientada à ação.`
      ].filter(Boolean).join('\n\n');

      const response = await fetch('/api/ia/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey,
          model,
          messages: [{ role: 'user', content: prompt }],
          temperature: 0.2
        })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error?.message || data.error || `Erro HTTP ${response.status}`);
      }
      return data?.choices?.[0]?.message?.content || 'Sem resposta da IA.';
    }

    async function initGenericIaWidget() {
      const pageConfig = IA_PAGE_CONFIG[path];
      if (!pageConfig) return;
      if (window.__iaChatWidgetMounted) return;
      if (document.querySelector('.ia-panel') || document.querySelector('.ia-fab')) return;
      await ensureIaWidgetScript();
      if (!window.IaChatWidget) return;
      if (window.__iaChatWidgetMounted) return;
      if (window.__iaChatWidgetInstances && window.__iaChatWidgetInstances[`page:${path}`]) return;
      window.IaChatWidget.create({
        singletonKey: `page:${path}`,
        title: pageConfig.title,
        subtitle: pageConfig.subtitle,
        buttonLabel: 'IA',
        buttonTitle: pageConfig.title,
        chatPlaceholder: pageConfig.chatPlaceholder,
        emptyMessage: pageConfig.emptyMessage,
        actions: pageConfig.actions,
        shortcuts: pageConfig.shortcuts,
        hasData: () => true,
        onRun: ({ action, question }) => runGenericIaRequest(pageConfig, action, question)
      });
    }
    setTimeout(() => { initGenericIaWidget().catch(() => {}); }, 250);

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

    // Theme selector (desktop + mobile)
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
        ddParent?.classList.remove('open');
        closeMobile();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDOM);
  } else {
    initDOM();
  }

})();

/* ── callIaFree: helper global com fallback automático entre modelos free ── */
window.callIaFree = async function callIaFree(messages, { temperature = 0.2, max_tokens = 1200 } = {}) {
  const api_key = (localStorage.getItem('api_openrouter_key') || '').trim();

  // Lista de modelos free em ordem de preferência
  const preferred = (localStorage.getItem('api_openrouter_modelo') || '').trim();
  const FREE_MODELS = [
    preferred,
    'meta-llama/llama-3.3-70b-instruct:free',
    'mistralai/mistral-7b-instruct:free',
    'google/gemma-2-9b-it:free',
    'qwen/qwen-2-7b-instruct:free',
    'opencode-go/deepseek-v4-flash',
    'openrouter/free'
  ].filter((v, i, a) => v && a.indexOf(v) === i); // deduplica e remove vazios

  const errors = [];

  for (const model of FREE_MODELS) {
    try {
      const resp = await fetch('/api/ia/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, api_key, messages, temperature, max_tokens })
      });

      // Erros que justificam tentar o próximo modelo
      if (resp.status === 429 || resp.status === 503 || resp.status === 502) {
        errors.push(`${model}: sobrecarregado (${resp.status})`);
        continue;
      }

      const data = await resp.json().catch(() => ({}));

      if (!resp.ok) {
        errors.push(`${model}: ${data?.error?.message || data?.error || resp.status}`);
        continue; // tenta próximo modelo
      }

      const content = (data?.choices?.[0]?.message?.content || '').trim();
      if (!content) { errors.push(`${model}: resposta vazia`); continue; }

      // Salva o modelo que funcionou
      if (model !== preferred) localStorage.setItem('api_openrouter_modelo', model);

      return content;
    } catch (e) {
      errors.push(`${model}: ${e.message}`);
    }
  }

  throw new Error('Todos os modelos gratuitos falharam:\n' + errors.join('\n'));
};
