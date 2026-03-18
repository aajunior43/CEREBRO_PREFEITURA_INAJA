class ConfirmDialog extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._resolve = null;
  }

  connectedCallback() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: contents; }
        .overlay {
          position: fixed; inset: 0;
          background: rgba(0,0,0,0.45); backdrop-filter: blur(2px);
          z-index: 10001; display: flex; align-items: center; justify-content: center;
          opacity: 0; visibility: hidden; transition: opacity 0.25s, visibility 0.25s;
          padding: 20px;
        }
        .overlay.open { opacity: 1; visibility: visible; }
        .dialog {
          background: var(--surface, #ffffff); border-radius: 16px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.25);
          border: 1px solid var(--border, rgba(0,0,0,0.07));
          max-width: 420px; width: 100%;
          transform: scale(0.95) translateY(10px);
          transition: transform 0.25s cubic-bezier(0.2,0.8,0.2,1);
          font-family: inherit;
        }
        .overlay.open .dialog { transform: scale(1) translateY(0); }
        .dialog-header {
          padding: 20px 24px 0; font-size: 16px; font-weight: 700;
          color: var(--text, #1e293b);
        }
        .dialog-body {
          padding: 12px 24px 20px; font-size: 14px; line-height: 1.6;
          color: var(--text-2, #3d4f63);
        }
        .dialog-footer {
          display: flex; justify-content: flex-end; gap: 10px;
          padding: 0 24px 20px;
        }
        button {
          padding: 10px 20px; border-radius: 10px; border: none;
          font-size: 13px; font-weight: 600; cursor: pointer;
          font-family: inherit; transition: all 0.15s;
        }
        .btn-cancel {
          background: var(--surface-2, #f7f9fc); color: var(--text-2, #3d4f63);
          border: 1px solid var(--border, rgba(0,0,0,0.07));
        }
        .btn-cancel:hover { background: var(--bg, #f0f4f8); }
        .btn-confirm {
          background: linear-gradient(135deg, var(--blue, #4f80c8), var(--blue-dark, #3a67ac));
          color: white; box-shadow: 0 4px 12px rgba(79,128,200,0.3);
        }
        .btn-confirm:hover { box-shadow: 0 6px 16px rgba(79,128,200,0.4); transform: translateY(-1px); }
        .btn-danger {
          background: linear-gradient(135deg, var(--red, #c74a4a), #a83535);
          color: white; box-shadow: 0 4px 12px rgba(199,74,74,0.3);
        }
        .btn-danger:hover { box-shadow: 0 6px 16px rgba(199,74,74,0.4); transform: translateY(-1px); }
      </style>
      <div class="overlay" id="overlay">
        <div class="dialog">
          <div class="dialog-header" id="title"></div>
          <div class="dialog-body" id="message"></div>
          <div class="dialog-footer">
            <button class="btn-cancel" id="btn-cancel">Cancelar</button>
            <button class="btn-confirm" id="btn-confirm">Confirmar</button>
          </div>
        </div>
      </div>`;

    this._overlay = this.shadowRoot.getElementById('overlay');
    this._title = this.shadowRoot.getElementById('title');
    this._message = this.shadowRoot.getElementById('message');
    this._btnCancel = this.shadowRoot.getElementById('btn-cancel');
    this._btnConfirm = this.shadowRoot.getElementById('btn-confirm');

    this._btnCancel.addEventListener('click', () => this._close(false));
    this._btnConfirm.addEventListener('click', () => this._close(true));
    this._overlay.addEventListener('click', (e) => {
      if (e.target === this._overlay) this._close(false);
    });

    window.confirmDialog = {
      show: (opts) => this.show(opts),
    };
  }

  show({ title = 'Confirmação', message = 'Deseja continuar?', confirmText = 'Confirmar', cancelText = 'Cancelar', danger = false, onConfirm } = {}) {
    this._title.textContent = title;
    this._message.textContent = message;
    this._btnConfirm.textContent = confirmText;
    this._btnCancel.textContent = cancelText;
    this._btnConfirm.className = danger ? 'btn-danger' : 'btn-confirm';
    this._onConfirm = onConfirm || null;
    this._overlay.classList.add('open');

    return new Promise((resolve) => {
      this._resolve = resolve;
    });
  }

  _close(confirmed) {
    this._overlay.classList.remove('open');
    if (confirmed && typeof this._onConfirm === 'function') {
      this._onConfirm();
    }
    if (this._resolve) {
      this._resolve(confirmed);
      this._resolve = null;
    }
    this._onConfirm = null;
  }
}

if (!customElements.get('confirm-dialog')) {
  customElements.define('confirm-dialog', ConfirmDialog);
}
