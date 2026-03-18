import './theme-toggle.js';

const NAV_ITEMS = {
  documentos: [
    { href: '/pages/documentos.html',           name: 'Centro de Documentos',    desc: 'Salvar e organizar arquivos' },
    { href: '/pages/rpa.html',                  name: 'RPA',                     desc: 'Recibo de Pagamento Autônomo' },
    { href: '/pages/pdf.html',                  name: 'Editor de PDF',           desc: 'Mesclar, dividir e proteger' },
    { href: '/pages/assistente-empenho.html',   name: 'Assistente de Empenho',   desc: 'Gerar descrição de empenho com IA' },
    { href: '/pages/visualizador.html',         name: 'Relatório de Empenhos',   desc: 'Visualizar e filtrar empenhos' },
    { href: '/pages/auditor.html',              name: 'Auditor de NF',           desc: 'Auditoria de notas fiscais com IA' },
    { href: '/pages/prazos.html',               name: 'Prazos',                  desc: 'Contratos e prazos críticos' },
    { href: '/pages/protocolo.html',            name: 'Protocolo',               desc: 'Ofícios, memorandos e documentos' },
    { href: '/pages/autentique-assinatura.html', name: 'Assinatura Digital',     desc: 'Enviar documento para assinatura' },
  ],
  financeiro: [
    { href: '/pages/tarifas-bancarias.html',    name: 'Análise de Tarifas Bancárias', desc: 'Leitura de extratos e encargos' },
    { href: '/pages/fornecimento.html',         name: 'Solicitações de Aquisição',    desc: 'Pedidos e fluxo de compras' },
    { href: '/pages/despesa-prefeitura.html',   name: 'Execução das Dotações',        desc: 'Consulta de despesas e dotações' },
    { href: '/pages/despesa-relatorios.html',   name: 'Comparativo Orçamentário',     desc: 'Comparar períodos e histórico' },
  ],
  ferramentas: [
    { href: '/pages/cnpj.html',                  name: 'Consulta de CNPJ',            desc: 'Consultar dados de empresas' },
    { href: '/pages/renomear.html',              name: 'Renomeador com IA',            desc: 'Padronizar nomes de documentos' },
    { href: '/pages/calculadora-diarias.html',   name: 'Calculadora de Diárias',       desc: 'Calcular diárias de viagens' },
    { href: '/pages/tarefas.html',               name: 'Painel de Tarefas',            desc: 'Gerenciar atividades' },
    { href: '/pages/calendario.html',            name: 'Calendário Administrativo',    desc: 'Calendário de pagamentos' },
    { href: '/pages/manual.html',                name: 'Manual do Sistema',            desc: 'Guia completo do sistema' },
  ],
};

window.NAV_ITEMS = NAV_ITEMS;

class AppHeader extends HTMLElement {
  constructor() {
    super();
    this._initialized = false;
  }

  static get observedAttributes() {
    return ['page-title', 'active-page'];
  }

  connectedCallback() {
    if (this._initialized) return;
    this._initialized = true;
    this._path = window.location.pathname;
    this._mode = this.getAttribute('mode') || 'default';
    this._injectCSS();
    this._initTheme();
    this.render();
    this._setupEventListeners();
    if (this._mode !== 'home') {
      this._injectBreadcrumb();
      this._injectBottomNav();
      this._injectFooter();
      this._syncConfig();
      this._initIaWidget();
    }
  }

  attributeChangedCallback(name, oldVal, newVal) {
    if (!this._initialized || oldVal === newVal) return;
    if (name === 'page-title') {
      const el = this.querySelector('.header-title p, #shd-page-title');
      if (el) el.textContent = newVal || 'Gestão Municipal';
    }
  }

  get _pageTitle() {
    return this.getAttribute('page-title') || 'Gestão Municipal';
  }

  get _activePage() {
    return this.getAttribute('active-page') || this._path;
  }

  _isActive(href) {
    const p = this._activePage;
    return p.endsWith(href.replace(/^\/pages\//, '')) || p === href;
  }

  _activeClass(href) {
    return this._isActive(href)
      ? ' style="background:var(--blue-light,rgba(37,99,235,.1));color:var(--blue,#2563eb);border-radius:8px;"'
      : '';
  }

  _initTheme() {
    const isDespesa = this._path.includes('/pages/despesa');
    const saved = isDespesa ? 'dark' : localStorage.getItem('theme');
    if (saved === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else if (saved === 'vintage') document.documentElement.setAttribute('data-theme', 'vintage');
    else document.documentElement.removeAttribute('data-theme');
  }

  _injectCSS() {
    if (!document.getElementById('shd-component-css')) {
      const link = document.createElement('link');
      link.id = 'shd-component-css';
      link.rel = 'stylesheet';
      link.href = '/static/css/components/header.css';
      document.head.appendChild(link);
    }
  }

  _buildGroupItems(items) {
    return items.map(i => `
      <a href="${i.href}" class="nav-group-item"${this._activeClass(i.href)}>
        <div class="nav-group-item-text">
          <span class="nav-group-item-name">${i.name}</span>
          <span class="nav-group-item-desc">${i.desc}</span>
        </div>
      </a>`).join('');
  }

  _buildMobileItems(items) {
    return items.map(i => `
      <a href="${i.href}" class="mobile-nav-item${this._isActive(i.href) ? ' active' : ''}" style="text-decoration:none;">
        ${i.name}
      </a>`).join('');
  }

  render() {
    if (this._mode === 'home') {
      this._renderHome();
    } else {
      this._renderSubpage();
    }
  }

  _renderHome() {
    this.innerHTML = `
    <header class="header">
      <div class="header-inner">
        <div class="header-left">
          <button class="hamburger" id="hamburger">
            <span></span><span></span><span></span>
          </button>
          <div class="header-brand">
            <img id="header-brasao" src="/static/img/brasao.png" alt="Brasão de Inajá" style="height:52px;width:auto;object-fit:contain;" />
            <div class="header-title">
              <h1>Prefeitura de Inajá</h1>
              <p>${this._pageTitle}</p>
            </div>
          </div>
        </div>
        <div class="header-right">
          <div class="month-nav">
            <button class="nav-btn" id="btn-prev-month" title="Mês anterior">&#8249;</button>
            <div class="month-display">
              <span class="month-name" id="current-month-name">Fevereiro</span>
              <span class="month-year" id="current-month-year">2026</span>
            </div>
            <button class="nav-btn" id="btn-next-month" title="Próximo mês">&#8250;</button>
          </div>
          <div class="dropdown">
            <button class="dropdown-toggle" id="dropdown-toggle"></button>
            <div class="dropdown-menu" id="dropdown-menu">
              <button class="dropdown-item" id="btn-logs" data-tooltip="Ver histórico de alterações">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
                </svg>
                Logs
              </button>
              <button class="dropdown-item theme-toggle" id="theme-toggle">
                <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                </svg>
                <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
                <span class="theme-label">Tema Claro</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>`;
  }

  _renderSubpage() {
    const isDespesa = this._path.includes('/pages/despesa');
    const themeNow = document.documentElement.getAttribute('data-theme') || 'light';
    const themeLabel = themeNow === 'dark' ? 'Tema Vintage' : themeNow === 'vintage' ? 'Tema Claro' : 'Tema Escuro';

    this.innerHTML = `
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
                <p id="shd-page-title">${this._pageTitle}</p>
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
              ${this._buildGroupItems(NAV_ITEMS.documentos)}
              <div class="nav-group-title">Financeiro</div>
              ${this._buildGroupItems(NAV_ITEMS.financeiro)}
              <div class="nav-group-title">Ferramentas</div>
              ${this._buildGroupItems(NAV_ITEMS.ferramentas)}
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

    <div class="mobile-nav" id="shd-mobile-nav">
      <div class="mobile-nav-header">
        <span>Menu</span>
        <button class="mobile-nav-close" id="shd-mobile-nav-close">&times;</button>
      </div>
      <a href="/" class="mobile-nav-item" style="text-decoration:none;">Credores Fixos</a>
      <a href="/pages/tarefas.html" class="mobile-nav-item${this._isActive('/pages/tarefas.html') ? ' active' : ''}" style="text-decoration:none;">Tarefas</a>
      <div class="mobile-nav-divider"></div>
      <div class="mobile-nav-label">Documentos</div>
      ${this._buildMobileItems(NAV_ITEMS.documentos)}
      <div class="mobile-nav-divider"></div>
      <div class="mobile-nav-label">Financeiro</div>
      ${this._buildMobileItems(NAV_ITEMS.financeiro)}
      <div class="mobile-nav-divider"></div>
      <div class="mobile-nav-label">Ferramentas</div>
      ${this._buildMobileItems(NAV_ITEMS.ferramentas)}
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
  }

  _toggleTheme() {
    const isDespesa = this._path.includes('/pages/despesa');
    if (isDespesa) return;
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
    this._syncThemeLabels();
  }

  _syncThemeLabels() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    let text = 'Tema Escuro';
    if (current === 'dark') text = 'Tema Vintage';
    if (current === 'vintage') text = 'Tema Claro';
    this.querySelectorAll('.shd-theme-label').forEach(el => { el.textContent = text; });
    document.querySelectorAll('.theme-label').forEach(el => { el.textContent = text; });
  }

  _openMobile() {
    document.getElementById('shd-hamburger')?.classList.add('active');
    document.getElementById('shd-mobile-nav')?.classList.add('open');
    document.getElementById('shd-mobile-overlay')?.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  _closeMobile() {
    document.getElementById('shd-hamburger')?.classList.remove('active');
    document.getElementById('shd-mobile-nav')?.classList.remove('open');
    document.getElementById('shd-mobile-overlay')?.classList.remove('open');
    document.body.style.overflow = '';
  }

  _setupEventListeners() {
    if (this._mode === 'home') {
      this._setupHomeListeners();
      return;
    }

    const self = this;
    document.getElementById('shd-hamburger')?.addEventListener('click', () => {
      const mobile = document.getElementById('shd-mobile-nav');
      if (!mobile) return;
      mobile.classList.contains('open') ? self._closeMobile() : self._openMobile();
    });
    document.getElementById('shd-mobile-nav-close')?.addEventListener('click', () => self._closeMobile());
    document.getElementById('shd-mobile-overlay')?.addEventListener('click', () => self._closeMobile());

    this.querySelectorAll('#shd-header .nav-group-btn').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const group = btn.closest('.nav-group');
        const isOpen = group.classList.contains('open');
        self.querySelectorAll('#shd-header .nav-group').forEach(g => g.classList.remove('open'));
        if (!isOpen) group.classList.add('open');
      });
    });
    this.querySelectorAll('#shd-header .nav-group-menu').forEach(menu => {
      menu.addEventListener('click', e => {
        if (e.target.tagName !== 'A' && !e.target.closest('a')) e.stopPropagation();
      });
    });

    const ddToggle = document.getElementById('shd-dropdown-toggle');
    const ddParent = ddToggle?.parentElement;
    ddToggle?.addEventListener('click', e => {
      e.stopPropagation();
      ddParent?.classList.toggle('open');
    });

    document.addEventListener('click', () => {
      this.querySelectorAll('#shd-header .nav-group').forEach(g => g.classList.remove('open'));
      ddParent?.classList.remove('open');
    });

    document.getElementById('shd-theme-toggle')?.addEventListener('click', () => {
      ddParent?.classList.remove('open');
      self._toggleTheme();
    });
    document.getElementById('shd-mobile-theme')?.addEventListener('click', () => {
      self._closeMobile();
      self._toggleTheme();
    });
  }

  _setupHomeListeners() {
    const ddToggle = document.getElementById('dropdown-toggle');
    const ddParent = ddToggle?.parentElement;
    ddToggle?.addEventListener('click', e => {
      e.stopPropagation();
      ddParent?.classList.toggle('open');
    });
    document.addEventListener('click', () => {
      ddParent?.classList.remove('open');
    });
  }

  _injectBreadcrumb() {
    const allPages = [
      ...NAV_ITEMS.documentos.map(i => ({...i, cat: 'Documentos'})),
      ...NAV_ITEMS.financeiro.map(i => ({...i, cat: 'Financeiro'})),
      ...NAV_ITEMS.ferramentas.map(i => ({...i, cat: 'Ferramentas'})),
    ];
    const currentPage = allPages.find(p => this._isActive(p.href));
    if (!currentPage) return;
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
      <span class="shd-bc-current">${currentPage.name}</span>`;
    this.insertAdjacentElement('afterend', crumb);
  }

  _injectBottomNav() {
    if (document.getElementById('shd-bottom-nav')) return;
    const self = this;
    const bnav = document.createElement('div');
    bnav.id = 'shd-bottom-nav';
    bnav.className = 'bottom-nav';
    bnav.innerHTML = `
      <div class="bottom-nav-items">
        <a class="bottom-nav-item${this._isActive('/') || this._isActive('/index.html') ? ' active':''}" href="/">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
          <span>Credores</span>
          <span class="bottom-nav-indicator"></span>
        </a>
        <a class="bottom-nav-item${this._isActive('/pages/tarefas.html') ? ' active':''}" href="/pages/tarefas.html">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
          <span>Tarefas</span>
          <span class="bottom-nav-indicator"></span>
        </a>
        <a class="bottom-nav-item${this._isActive('/pages/cnpj.html') ? ' active':''}" href="/pages/cnpj.html">
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
      mobile.classList.contains('open') ? self._closeMobile() : self._openMobile();
    });
  }

  _injectFooter() {
    if (document.querySelector('.shd-footer')) return;
    document.body.insertAdjacentHTML('beforeend',
      `<footer class="shd-footer">Desenvolvido por <strong>Aleksandro Alves</strong></footer>`);
  }

  _syncConfig() {
    if (!localStorage.getItem('api_openrouter_key')) {
      fetch('/api/config').then(r => r.json()).then(cfg => {
        if (cfg.api_openrouter_key)    { localStorage.setItem('api_openrouter_key', cfg.api_openrouter_key); localStorage.setItem('ext_ia_key', cfg.api_openrouter_key); }
        if (cfg.api_openrouter_modelo) { localStorage.setItem('api_openrouter_modelo', cfg.api_openrouter_modelo); localStorage.setItem('ext_ia_modelo', cfg.api_openrouter_modelo); }
        if (cfg.api_cnpja_key)         { localStorage.setItem('api_cnpja_key', cfg.api_cnpja_key); }
      }).catch(() => {});
    }
  }

  _initIaWidget() {
    const path = this._path;
    const IA_PAGE_CONFIG = {
      '/pages/protocolo.html': {
        title: 'IA de Protocolo', subtitle: 'Assistente para ofícios, memorandos e acompanhamento documental',
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
          const rows = Array.from(document.querySelectorAll('.pr-item')).slice(0, 20).map(item => ({
            numero: item.querySelector('.pr-item-num')?.textContent?.trim() || '',
            assunto: item.querySelector('.pr-item-title')?.textContent?.trim() || '',
            meta: item.querySelector('.pr-item-meta')?.textContent?.replace(/\s+/g, ' ')?.trim() || '',
            obs: item.querySelector('.pr-item-desc')?.textContent?.trim() || ''
          }));
          return { page: 'protocolo', protocolos_visiveis: rows };
        }
      },
      '/pages/prazos.html': {
        title: 'IA de Prazos', subtitle: 'Assistente para contratos, vencimentos e notificações',
        chatPlaceholder: 'Ex: Quais prazos estão mais críticos hoje?',
        emptyMessage: 'Cadastre ou carregue prazos antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume os prazos e principais pontos de atenção.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Ordena o que precisa de ação imediata.' },
          { id: 'riscos', label: 'Riscos', description: 'Aponta atrasos, vencimentos próximos e exposições.' },
          { id: 'chat', label: 'Chat', description: 'Permite perguntar livremente sobre os prazos.' }
        ],
        shortcuts: [
          { label: 'Resumo dos prazos', action: 'analisar' },
          { label: 'Urgências do dia', action: 'prioridades' },
          { label: 'Riscos e atrasos', action: 'riscos' }
        ]
      },
      '/pages/documentos.html': {
        title: 'IA de Documentos', subtitle: 'Assistente para organização documental e critérios de arquivamento',
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
        title: 'IA de Aquisições', subtitle: 'Assistente para pedidos, fornecedores e fluxo de compras',
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
        title: 'IA de CNPJ', subtitle: 'Assistente para leitura de cadastro empresarial e checagens rápidas',
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
        title: 'IA de PDF', subtitle: 'Assistente para orientar fusão, divisão, proteção e organização de arquivos',
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
        title: 'IA de RPA', subtitle: 'Assistente para conferência e preenchimento de recibos',
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
        title: 'IA do Manual', subtitle: 'Assistente para orientar o uso do sistema e localizar instruções',
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
        title: 'IA de Empenhos', subtitle: 'Assistente para leitura, filtros e interpretação de empenhos',
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
        title: 'IA do Calendário', subtitle: 'Assistente para organização de eventos, pagamentos e compromissos',
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
        title: 'IA de Diárias', subtitle: 'Assistente para cálculo, revisão e conferência de diárias',
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
        title: 'IA de Assinatura Digital', subtitle: 'Assistente para conferência de envios, signatários e pendências',
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
        title: 'IA de Auditoria', subtitle: 'Assistente para leitura de NF, inconsistências e validação',
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
        title: 'IA de Empenho', subtitle: 'Assistente para compor e revisar descrições de empenho',
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
        title: 'IA de Extratos', subtitle: 'Assistente para leitura e organização de extratos importados',
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
        title: 'IA do Gerador de Empenho', subtitle: 'Assistente para revisar entradas e orientar a geração do texto',
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
        title: 'IA do Renomeador', subtitle: 'Assistente para padronização e estratégia de nomes de arquivos',
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
        title: 'IA Orçamentária', subtitle: 'Assistente de análise de dotações',
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
          return _buildGenericIaContext(path);
        }
      },
      '/pages/despesa-relatorios.html': {
        title: 'IA dos Relatórios', subtitle: 'Assistente comparativo de dotações',
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
          return _buildGenericIaContext(path);
        }
      },
      '/pages/tarifas-bancarias.html': {
        title: 'IA Financeira', subtitle: 'Assistente para leitura de extratos e tarifas',
        chatPlaceholder: 'Ex: Há alguma tarifa indevida neste extrato?',
        emptyMessage: 'Envie um extrato e gere a análise antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume o extrato, custos e principais achados.' },
          { id: 'anomalias', label: 'Anomalias', description: 'Procura cobranças estranhas e riscos.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Mostra o que conferir primeiro no extrato.' },
          { id: 'chat', label: 'Chat', description: 'Pergunta livre sobre o extrato.' }
        ],
        shortcuts: [
          { label: 'Resumo do extrato', action: 'analisar' },
          { label: 'Tarifas suspeitas', action: 'anomalias' }
        ],
        contextBuilder() {
          if (typeof window.buildFinancialContext === 'function') return window.buildFinancialContext();
          return _buildGenericIaContext(path);
        }
      },
      '/pages/tarefas.html': {
        title: 'IA de Tarefas', subtitle: 'Assistente para organização de atividades e prioridades',
        chatPlaceholder: 'Ex: Quais tarefas devo focar para terminar o dia bem?',
        emptyMessage: 'Cadastre tarefas antes de usar a IA.',
        actions: [
          { id: 'analisar', label: 'Analisar', description: 'Resume o quadro de tarefas e gargalos.' },
          { id: 'prioridades', label: 'Prioridades', description: 'Ordena o que deve ser feito primeiro.' },
          { id: 'riscos', label: 'Riscos', description: 'Aponta atrasos e tarefas críticas.' },
          { id: 'chat', label: 'Chat', description: 'Pergunta livre sobre suas tarefas.' }
        ],
        shortcuts: [
          { label: 'Resumo do quadro', action: 'analisar' },
          { label: 'O que fazer hoje', action: 'prioridades' }
        ],
        contextBuilder() {
          if (typeof window.buildKanbanContext === 'function') return window.buildKanbanContext();
          return _buildGenericIaContext(path);
        }
      }
    };

    function ensureIaWidgetScript() {
      return new Promise(resolve => {
        if (window.IaChatWidget) { resolve(); return; }
        const existing = document.querySelector('script[data-ia-chat-widget-script]');
        if (existing) { existing.addEventListener('load', () => resolve(), { once: true }); setTimeout(resolve, 1500); return; }
        const script = document.createElement('script');
        script.src = '/static/js/ia-chat-widget.js';
        script.async = true;
        script.setAttribute('data-ia-chat-widget-script', 'true');
        script.onload = () => resolve();
        script.onerror = () => resolve();
        document.head.appendChild(script);
      });
    }

    async function runGenericIaRequest(pageConfig, action, question) {
      const apiKey = localStorage.getItem('api_openrouter_key') || localStorage.getItem('ext_ia_key') || '';
      if (!apiKey && !pageConfig.endpoint) throw new Error('Configure a chave OpenRouter em ADM antes de usar a IA.');
      const model = localStorage.getItem('api_openrouter_modelo') || localStorage.getItem('ext_ia_modelo') || 'openrouter/free';
      const context = typeof pageConfig.contextBuilder === 'function' ? pageConfig.contextBuilder() : _buildGenericIaContext(path);
      if (pageConfig.endpoint) {
        const resp = await fetch(pageConfig.endpoint, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
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
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, model, messages: [{ role: 'user', content: prompt }], temperature: 0.2 })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error?.message || data.error || `Erro HTTP ${response.status}`);
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
  }
}

function _buildGenericIaContext(path) {
  const title = document.title || path;
  const heading = document.querySelector('h1, h2')?.textContent?.trim() || '';
  const text = Array.from(document.querySelectorAll('main, section, .content, .page-wrap, .docs-wrap, .pr-wrap, .pz-wrap, .viz-app'))
    .map(el => el.textContent || '')
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 6000);
  return { page_path: path, page_title: title, page_heading: heading, visible_text: text };
}

window.callIaFree = async function callIaFree(messages, { temperature = 0.2, max_tokens = 1200 } = {}) {
  const api_key = (localStorage.getItem('api_openrouter_key') || '').trim();
  const preferred = (localStorage.getItem('api_openrouter_modelo') || '').trim();
  const FREE_MODELS = [
    preferred,
    'meta-llama/llama-3.3-70b-instruct:free',
    'mistralai/mistral-7b-instruct:free',
    'google/gemma-2-9b-it:free',
    'qwen/qwen-2-7b-instruct:free',
    'openrouter/free'
  ].filter((v, i, a) => v && a.indexOf(v) === i);
  const errors = [];
  for (const model of FREE_MODELS) {
    try {
      const resp = await fetch('/api/ia/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, api_key, messages, temperature, max_tokens })
      });
      if (resp.status === 429 || resp.status === 503 || resp.status === 502) {
        errors.push(`${model}: sobrecarregado (${resp.status})`); continue;
      }
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) { errors.push(`${model}: ${data?.error?.message || data?.error || resp.status}`); continue; }
      const content = (data?.choices?.[0]?.message?.content || '').trim();
      if (!content) { errors.push(`${model}: resposta vazia`); continue; }
      if (model !== preferred) localStorage.setItem('api_openrouter_modelo', model);
      return content;
    } catch (e) { errors.push(`${model}: ${e.message}`); }
  }
  throw new Error('Todos os modelos gratuitos falharam:\n' + errors.join('\n'));
};

if (!customElements.get('app-header')) {
  customElements.define('app-header', AppHeader);
}
