class ToastNotification extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._toasts = [];
  }

  connectedCallback() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          position: fixed; bottom: 24px; right: 24px;
          z-index: 10000; display: flex; flex-direction: column-reverse;
          gap: 8px; pointer-events: none;
        }
        .toast {
          display: flex; align-items: center; gap: 10px;
          padding: 14px 20px; border-radius: 12px;
          font-size: 13px; font-weight: 600; font-family: inherit;
          box-shadow: 0 8px 30px rgba(0,0,0,0.18);
          pointer-events: auto; min-width: 260px; max-width: 420px;
          animation: slideIn 0.3s cubic-bezier(0.2,0.8,0.2,1);
          transition: opacity 0.3s, transform 0.3s;
        }
        .toast.removing {
          opacity: 0; transform: translateX(40px);
        }
        .toast.success {
          background: var(--green-bg, #d4f5e3); color: var(--green-dark, #2d8a59);
          border: 1px solid rgba(58,170,110,0.3);
        }
        .toast.error {
          background: var(--red-bg, #fdd8d8); color: var(--red, #c74a4a);
          border: 1px solid rgba(199,74,74,0.3);
        }
        .toast.info {
          background: var(--blue-light, #dde9ff); color: var(--blue-dark, #3a67ac);
          border: 1px solid rgba(79,128,200,0.3);
        }
        .toast.warning {
          background: var(--orange-bg, #fde8d4); color: var(--orange, #d97c3a);
          border: 1px solid rgba(217,124,58,0.3);
        }
        .toast svg { width: 18px; height: 18px; flex-shrink: 0; }
        .toast .msg { flex: 1; }
        .toast .close-btn {
          background: none; border: none; color: inherit; cursor: pointer;
          opacity: 0.6; padding: 2px; font-size: 16px; line-height: 1;
        }
        .toast .close-btn:hover { opacity: 1; }
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(40px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @media (max-width: 600px) {
          :host { bottom: 80px; right: 12px; left: 12px; }
          .toast { min-width: auto; max-width: 100%; }
        }
      </style>
      <div id="container"></div>`;

    window.toast = {
      success: (msg, duration) => this._show(msg, 'success', duration),
      error: (msg, duration) => this._show(msg, 'error', duration),
      info: (msg, duration) => this._show(msg, 'info', duration),
      warning: (msg, duration) => this._show(msg, 'warning', duration),
    };

    if (typeof window.showToast === 'function') {
      this._origShowToast = window.showToast;
    }
    window.showToast = (msg, type) => {
      const t = type || 'info';
      this._show(msg, t === 'success' ? 'success' : t === 'error' ? 'error' : t === 'warning' ? 'warning' : 'info');
    };
  }

  _icons = {
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>',
    error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
  };

  _show(msg, type = 'info', duration = 4000) {
    const container = this.shadowRoot.getElementById('container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `${this._icons[type] || this._icons.info}<span class="msg">${msg}</span><button class="close-btn">&times;</button>`;

    const remove = () => {
      el.classList.add('removing');
      setTimeout(() => el.remove(), 300);
    };

    el.querySelector('.close-btn').addEventListener('click', remove);
    container.appendChild(el);

    if (duration > 0) {
      setTimeout(remove, duration);
    }
  }

  disconnectedCallback() {
    if (this._origShowToast) window.showToast = this._origShowToast;
  }
}

if (!customElements.get('toast-notification')) {
  customElements.define('toast-notification', ToastNotification);
}
