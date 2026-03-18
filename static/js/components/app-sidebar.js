class AppSidebar extends HTMLElement {
  constructor() {
    super();
    this._initialized = false;
  }

  connectedCallback() {
    if (this._initialized) return;
    this._initialized = true;
    this._injectCSS();
    this.render();
    this._setupListeners();
  }

  _injectCSS() {
    if (!document.getElementById('shd-sidebar-css')) {
      const link = document.createElement('link');
      link.id = 'shd-sidebar-css';
      link.rel = 'stylesheet';
      link.href = '/static/css/components/sidebar.css';
      document.head.appendChild(link);
    }
  }

  render() {
    this.innerHTML = `
    <aside class="app-sidebar" id="app-sidebar">
      <div class="sidebar-scroll">

        <div class="sidebar-section" style="padding-bottom:0">
          <button class="nav-home-btn active" id="btn-home-screen">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
            Início
          </button>
        </div>

        <div class="sidebar-expand-all-wrap">
          <button class="sidebar-expand-all-btn" id="btn-sidebar-expand-all" title="Expandir ou recolher todos os grupos do menu">
            <svg id="sidebar-expand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
            <span id="sidebar-expand-label">Expandir tudo</span>
          </button>
        </div>

        <div class="sidebar-section">
          <div class="sidebar-label">Operação</div>
          <button class="nav-tab active nav-tab-sidebar" data-tab="credores-fixos" data-tooltip="Lista de credores com empenhos mensais">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            <span>Credores Fixos</span>
          </button>
          <a href="/pages/tarefas.html" class="nav-group-item nav-group-item-inline">
            <div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg></div>
            <div class="nav-group-item-text"><span class="nav-group-item-name">Tarefas</span><span class="nav-group-item-desc">Gerenciar atividades</span></div>
          </a>
          <a href="/pages/calendario.html" class="nav-group-item nav-group-item-inline">
            <div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>
            <div class="nav-group-item-text"><span class="nav-group-item-name">Calendário</span><span class="nav-group-item-desc">Histórico mensal</span></div>
          </a>
        </div>

        <div class="sidebar-section">
          <div class="sidebar-label">Financeiro</div>
          <div class="nav-group open nav-group-sidebar">
            <button class="nav-group-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8v1m0 9v1"/></svg>
              Financeiro
              <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <div class="nav-group-menu nav-group-menu-sidebar">
              <a href="/pages/tarifas-bancarias.html" class="nav-group-item">
                <div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8v1m0 9v1"/></svg></div>
                <div class="nav-group-item-text"><span class="nav-group-item-name">Tarifas</span><span class="nav-group-item-desc">Encargos e tarifas bancárias</span></div>
              </a>
              <a href="/pages/fornecimento.html" class="nav-group-item">
                <div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg></div>
                <div class="nav-group-item-text"><span class="nav-group-item-name">Aquisições</span><span class="nav-group-item-desc">Controle de fornecedores</span></div>
              </a>
              <a href="/pages/despesa-prefeitura.html" class="nav-group-item">
                <div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg></div>
                <div class="nav-group-item-text"><span class="nav-group-item-name">Dotações Orçamentárias</span><span class="nav-group-item-desc">Dotações e execução orçamentária</span></div>
              </a>
              <a href="/pages/despesa-relatorios.html" class="nav-group-item">
                <div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M7 16l4-4 4 4 4-4"/></svg></div>
                <div class="nav-group-item-text"><span class="nav-group-item-name">Relatórios</span><span class="nav-group-item-desc">Comparar períodos e histórico</span></div>
              </a>
            </div>
          </div>
        </div>

        <div class="sidebar-section">
          <div class="sidebar-label">Documentos</div>
          <div class="nav-group open nav-group-sidebar">
            <button class="nav-group-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              Documentos
              <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <div class="nav-group-menu nav-group-menu-sidebar">
              <a href="/pages/documentos.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">Centro de Documentos</span><span class="nav-group-item-desc">Salvar e organizar arquivos</span></div></a>
              <a href="/pages/rpa.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">RPA</span><span class="nav-group-item-desc">Recibo de Pagamento Autônomo</span></div></a>
              <a href="/pages/pdf.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M10 13h4m-2-2v4"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">PDF</span><span class="nav-group-item-desc">Mesclar, dividir e proteger</span></div></a>
              <a href="/pages/assistente-empenho.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.813 15.904L9 18.75l2.846-.813a1.125 1.125 0 00.41-.192l6.83-6.83a2.812 2.812 0 10-3.98-3.98l-6.83 6.83a1.125 1.125 0 00-.192.41z"/><path d="M5 5h.01"/><path d="M19 19h.01"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">Assistente de Empenho</span><span class="nav-group-item-desc">IA para descricao e conferencia</span></div></a>
              <a href="/pages/visualizador.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12c0 1.2-4.03 6-9 6s-9-4.8-9-6c0-1.2 4.03-6 9-6s9 4.8 9 6z"/><circle cx="12" cy="12" r="3"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">Rel. de Empenhos</span><span class="nav-group-item-desc">Documentos e contratos</span></div></a>
              <a href="/pages/auditor.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">Auditor NF</span><span class="nav-group-item-desc">Auditoria e notas fiscais</span></div></a>
              <a href="/pages/prazos.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">Prazos</span><span class="nav-group-item-desc">Contratos e prazos críticos</span></div></a>
              <a href="/pages/protocolo.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">Protocolo</span><span class="nav-group-item-desc">Ofícios e memorandos</span></div></a>
              <a href="/pages/autentique-assinatura.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4Z"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">Assinatura Digital</span><span class="nav-group-item-desc">Autentique e envio por WhatsApp</span></div></a>
            </div>
          </div>
        </div>

        <div class="sidebar-section">
          <div class="sidebar-label">Ferramentas</div>
          <div class="nav-group open nav-group-sidebar">
            <button class="nav-group-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
              Ferramentas
              <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <div class="nav-group-menu nav-group-menu-sidebar">
              <a href="/pages/cnpj.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><line x1="12" y1="12" x2="12" y2="16"/><line x1="10" y1="14" x2="14" y2="14"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">CNPJ</span><span class="nav-group-item-desc">Consultar dados de empresas</span></div></a>
              <a href="/pages/renomear.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">Renomear com IA</span><span class="nav-group-item-desc">Organizar PDFs e extratos</span></div></a>
              <a href="/pages/calculadora-diarias.html" class="nav-group-item"><div class="nav-group-item-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="2" width="18" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="16" y2="18"/><line x1="12" y1="14" x2="16" y2="14"/><line x1="8" y1="18" x2="8.01" y2="18"/><line x1="8" y1="14" x2="8.01" y2="14"/><line x1="8" y1="10" x2="8.01" y2="10"/><line x1="12" y1="10" x2="16" y2="10"/><line x1="8" y1="6" x2="16" y2="6"/></svg></div><div class="nav-group-item-text"><span class="nav-group-item-name">Calc. Diárias</span><span class="nav-group-item-desc">Cálculo de diárias de viagem</span></div></a>
              <a href="/pages/manual.html" class="nav-group-item"><div class="nav-group-item-icon">📖</div><div class="nav-group-item-text"><span class="nav-group-item-name">Manual</span><span class="nav-group-item-desc">Guia completo do sistema</span></div></a>
            </div>
          </div>
        </div>

        <div class="sidebar-section sidebar-section-admin">
          <div class="sidebar-label">Administração</div>
          <button class="nav-tab nav-tab-sidebar nav-tab-admin" data-tab="adm" data-requires-auth="true" data-tooltip="Configurações de API e sistema">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
            <span>ADM</span>
          </button>
          <button class="nav-tab nav-tab-sidebar" id="sidebar-logs">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            <span>Logs</span>
          </button>
          <button class="nav-tab nav-tab-sidebar theme-toggle" id="sidebar-theme-toggle">
            <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
            <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            <span class="theme-label-sidebar">Tema</span>
          </button>
        </div>
      </div>
    </aside>`;
  }

  _setupListeners() {
    const expandBtn = this.querySelector('#btn-sidebar-expand-all');
    const expandLabel = this.querySelector('#sidebar-expand-label');
    const expandIcon = this.querySelector('#sidebar-expand-icon');

    if (expandBtn) {
      const sidebarGroups = () => this.querySelectorAll('.nav-group-sidebar');
      const allOpen = () => [...sidebarGroups()].every(g => g.classList.contains('open'));

      expandBtn.addEventListener('click', () => {
        if (allOpen()) {
          sidebarGroups().forEach(g => g.classList.remove('open'));
          expandBtn.classList.remove('expanded');
          if (expandLabel) expandLabel.textContent = 'Expandir tudo';
        } else {
          sidebarGroups().forEach(g => g.classList.add('open'));
          expandBtn.classList.add('expanded');
          if (expandLabel) expandLabel.textContent = 'Recolher tudo';
        }
      });
    }
  }
}

if (!customElements.get('app-sidebar')) {
  customElements.define('app-sidebar', AppSidebar);
}
