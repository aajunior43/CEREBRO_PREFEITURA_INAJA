/**
 * Toast Notifications — Sistema de notificações visuais
 * 
 * Uso:
 *   Toast.success('Salvo!', 'Dados atualizados com sucesso.')
 *   Toast.error('Erro', 'Não foi possível conectar ao servidor.')
 *   Toast.warning('Atenção', 'Sessão expirando em 5 minutos.')
 *   Toast.info('Info', 'Backup concluído.')
 * 
 * Erros HTTP automáticos:
 *   Toast.handleHttpError(response) — chama após fetch()
 *   Toast.interceptFetch() — intercepta globalmente
 */

class Toast {
  static container = null
  static toasts = []
  static defaultDuration = 5000
  static maxToasts = 5

  // ── Ícones SVG ──────────────────────────────────────────────
  static icons = {
    success: `<svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
    error: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><line x1="15" y1="9" x2="9" y2="15" stroke="currentColor" stroke-width="2"/><line x1="9" y1="9" x2="15" y2="15" stroke="currentColor" stroke-width="2"/></svg>`,
    warning: `<svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" fill="none" stroke="currentColor" stroke-width="2"/><line x1="12" y1="9" x2="12" y2="13" stroke="currentColor" stroke-width="2"/><line x1="12" y1="17" x2="12.01" y2="17" stroke="currentColor" stroke-width="2"/></svg>`,
    info: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><line x1="12" y1="16" x2="12" y2="12" stroke="currentColor" stroke-width="2"/><line x1="12" y1="8" x2="12.01" y2="8" stroke="currentColor" stroke-width="2"/></svg>`,
    close: `<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`
  }

  // ── Inicialização ──────────────────────────────────────────
  static init() {
    if (this.container) return
    
    this.container = document.createElement('div')
    this.container.id = 'toast-container'
    document.body.appendChild(this.container)
  }

  // ── Métodos Públicos ───────────────────────────────────────
  static success(title, message, options = {}) {
    return this.show('success', title, message, options)
  }

  static error(title, message, options = {}) {
    return this.show('error', title, message, options)
  }

  static warning(title, message, options = {}) {
    return this.show('warning', title, message, options)
  }

  static info(title, message, options = {}) {
    return this.show('info', title, message, options)
  }

  // ── Erros HTTP ─────────────────────────────────────────────
  static handleHttpError(error, context = '') {
    const errorInfo = this.parseHttpError(error, context)
    return this.show(
      errorInfo.type,
      errorInfo.title,
      errorInfo.message,
      { duration: errorInfo.duration }
    )
  }

  static async handleFetchResponse(response, options = {}) {
    if (response.ok) return response
    
    // Parse error body
    let errorMessage = `HTTP ${response.status}`
    try {
      const data = await response.json()
      errorMessage = data.error?.message || data.message || errorMessage
    } catch {
      // Ignore
    }
    
    this.handleHttpError({
      status: response.status,
      message: errorMessage,
      url: response.url
    }, options.context)
    
    return response
  }

  // ── Interceptação Global de Fetch ──────────────────────────
  static interceptFetch() {
    if (window._fetchIntercepted) return
    
    const originalFetch = window.fetch
    window._fetchIntercepted = true
    
    window.fetch = async function(...args) {
      try {
        const response = await originalFetch.apply(this, args)
        
        // Não interceptar respostas OK
        if (response.ok) return response
        
        // Interceptar erros HTTP
        if ([401, 403, 429, 500, 502, 503].includes(response.status)) {
          await Toast.handleFetchResponse(response, {
            context: args[0] || 'unknown'
          })
        }
        
        return response
      } catch (error) {
        // Erros de rede
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
          Toast.error(
            'Erro de Conexão',
            'Verifique sua conexão com a internet.',
            { duration: 6000 }
          )
        }
        throw error
      }
    }
  }

  // ── Show Toast ─────────────────────────────────────────────
  static show(type, title, message, options = {}) {
    this.init()
    
    // Limitar número de toasts
    if (this.toasts.length >= this.maxToasts) {
      const oldest = this.toasts.shift()
      this.remove(oldest, false)
    }
    
    const duration = options.duration || this.defaultDuration
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    
    const toast = document.createElement('div')
    toast.className = `toast toast-${type}`
    toast.id = id
    toast.setAttribute('role', 'alert')
    toast.setAttribute('aria-live', 'assertive')
    
    toast.innerHTML = `
      <div class="toast-icon">${this.icons[type] || this.icons.info}</div>
      <div class="toast-content">
        ${title ? `<div class="toast-title">${this.escapeHtml(title)}</div>` : ''}
        ${message ? `<div class="toast-message">${this.escapeHtml(message)}</div>` : ''}
      </div>
      <button class="toast-close" aria-label="Fechar">${this.icons.close}</button>
      ${duration > 0 ? `<div class="toast-progress" style="animation-duration: ${duration}ms"></div>` : ''}
    `
    
    this.container.appendChild(toast)
    this.toasts.push({ id, element: toast })
    
    // Close button
    toast.querySelector('.toast-close').addEventListener('click', () => {
      this.remove({ id, element: toast })
    })
    
    // Auto-dismiss
    if (duration > 0) {
      setTimeout(() => {
        this.remove({ id, element: toast })
      }, duration)
    }
    
    return id
  }

  // ── Remove Toast ───────────────────────────────────────────
  static remove(toast, animate = true) {
    if (!toast?.element) return
    
    if (animate) {
      toast.element.classList.add('toast-exiting')
      setTimeout(() => {
        toast.element.remove()
        this.toasts = this.toasts.filter(t => t.id !== toast.id)
      }, 300)
    } else {
      toast.element.remove()
      this.toasts = this.toasts.filter(t => t.id !== toast.id)
    }
  }

  // ── Parse HTTP Error ───────────────────────────────────────
  static parseHttpError(error, context = '') {
    const status = error.status || error.response?.status || 0
    const message = error.message || error.error?.message || ''
    
    const handlers = {
      400: () => ({
        type: 'error',
        title: 'Requisição Inválida',
        message: message || 'Verifique os dados enviados e tente novamente.',
        duration: 5000
      }),
      401: () => ({
        type: 'unauthorized',
        title: 'Não Autorizado',
        message: 'Sessão expirada ou credenciais inválidas. Faça login novamente.',
        duration: 6000
      }),
      403: () => ({
        type: 'error',
        title: 'Acesso Negado',
        message: 'Você não tem permissão para acessar este recurso.',
        duration: 5000
      }),
      404: () => ({
        type: 'warning',
        title: 'Não Encontrado',
        message: message || 'Recurso não encontrado.',
        duration: 4000
      }),
      409: () => ({
        type: 'warning',
        title: 'Conflito',
        message: message || 'Já existe um registro com estes dados.',
        duration: 5000
      }),
      422: () => ({
        type: 'error',
        title: 'Dados Inválidos',
        message: message || 'Verifique os campos e tente novamente.',
        duration: 5000
      }),
      429: () => ({
        type: 'rate-limit',
        title: 'Muitas Requisições',
        message: 'Aguarde alguns instantes antes de tentar novamente.',
        duration: 6000
      }),
      500: () => ({
        type: 'server-error',
        title: 'Erro do Servidor',
        message: 'Erro interno do servidor. Tente novamente em instantes.',
        duration: 6000
      }),
      502: () => ({
        type: 'server-error',
        title: 'Serviço Indisponível',
        message: 'Serviço externo temporariamente indisponível.',
        duration: 6000
      }),
      503: () => ({
        type: 'server-error',
        title: 'Serviço Indisponível',
        message: 'Sistema em manutenção. Tente novamente em breve.',
        duration: 6000
      })
    }
    
    const handler = handlers[status]
    if (handler) return handler()
    
    // Erro genérico
    return {
      type: 'error',
      title: 'Erro',
      message: message || 'Ocorreu um erro inesperado.',
      duration: 5000
    }
  }

  // ── Escape HTML ────────────────────────────────────────────
  static escapeHtml(text) {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  // ── Limpar Todos ───────────────────────────────────────────
  static clearAll() {
    this.toasts.forEach(toast => this.remove(toast, true))
  }
}

// Exportar para window
window.Toast = Toast

// Auto-inicializar quando DOM estiver pronto
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => Toast.init())
} else {
  Toast.init()
}

// Interceptar fetch automaticmente
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => Toast.interceptFetch())
} else {
  Toast.interceptFetch()
}
