class ThemeToggle extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._locked = false;
  }

  connectedCallback() {
    this._locked = this.hasAttribute('locked');
    this.render();
    this._setupListeners();
    this._sync();
  }

  static get observedAttributes() {
    return ['locked'];
  }

  attributeChangedCallback(name, oldVal, newVal) {
    if (name === 'locked') this._locked = newVal !== null;
  }

  get theme() {
    return document.documentElement.getAttribute('data-theme') || 'light';
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: inline-flex; }
        button {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 12px; background: none; border: none;
          border-radius: var(--radius-sm, 8px); color: var(--text-2, #3d4f63);
          font-size: 13px; font-weight: 500; cursor: pointer;
          text-align: left; transition: all 0.15s; font-family: inherit;
          width: 100%;
        }
        button:hover { background: rgba(79,128,200,0.1); color: var(--blue, #4f80c8); }
        svg { width: 18px; height: 18px; flex-shrink: 0; }
        .icon-moon { display: none; }
        :host([theme="dark"]) .icon-sun { display: none; }
        :host([theme="dark"]) .icon-moon { display: block; }
        :host([theme="vintage"]) .icon-sun { display: none; }
        :host([theme="vintage"]) .icon-moon { display: block; }
      </style>
      <button part="button">
        <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
        </svg>
        <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
        <span class="label"></span>
      </button>`;
  }

  _sync() {
    const current = this.theme;
    this.setAttribute('theme', current);
    const label = this.shadowRoot.querySelector('.label');
    if (!label) return;
    if (current === 'light') label.textContent = 'Tema Escuro';
    else if (current === 'dark') label.textContent = 'Tema Vintage';
    else label.textContent = 'Tema Claro';
  }

  _setupListeners() {
    this.shadowRoot.querySelector('button').addEventListener('click', () => {
      if (this._locked) return;
      const current = this.theme;
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
      this._sync();
      this.dispatchEvent(new CustomEvent('theme-changed', {
        bubbles: true, composed: true,
        detail: { theme: this.theme }
      }));
    });

    this._observer = new MutationObserver(() => this._sync());
    this._observer.observe(document.documentElement, {
      attributes: true, attributeFilter: ['data-theme']
    });
  }

  disconnectedCallback() {
    if (this._observer) this._observer.disconnect();
  }
}

if (!customElements.get('theme-toggle')) {
  customElements.define('theme-toggle', ThemeToggle);
}
