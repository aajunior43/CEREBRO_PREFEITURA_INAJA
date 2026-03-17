(function () {
  'use strict';

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderMarkdownLite(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/^### (.+)$/gm, '<strong style="font-size:13px">$1</strong>')
      .replace(/^## (.+)$/gm, '<strong style="font-size:14px">$1</strong>')
      .replace(/^# (.+)$/gm, '<strong style="font-size:15px">$1</strong>');
  }

  function ensureStylesLoaded() {
    if (document.querySelector('link[data-ia-chat-widget]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/ia-chat-widget.css';
    link.setAttribute('data-ia-chat-widget', 'true');
    document.head.appendChild(link);
  }

  function createEl(tag, className, html) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (typeof html === 'string') el.innerHTML = html;
    return el;
  }

  function normalizeActions(actions) {
    return Array.isArray(actions) ? actions : [];
  }

  window.IaChatWidget = {
    create(config) {
      ensureStylesLoaded();

      const actions = normalizeActions(config.actions);
      const shortcuts = normalizeActions(config.shortcuts);
      let activeAction = config.defaultAction || (actions[0] && actions[0].id) || 'chat';

      const fab = createEl('button', 'iaw-fab');
      fab.type = 'button';
      fab.title = config.buttonTitle || 'Abrir IA';
      fab.textContent = config.buttonLabel || 'IA';

      const panel = createEl('div', 'iaw-panel');
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-label', config.title || 'Assistente IA');
      panel.innerHTML = `
        <div class="iaw-head">
          <div class="iaw-head-main">
            <span class="iaw-title">${escapeHtml(config.title || 'Assistente IA')}</span>
            <span class="iaw-subtitle">${escapeHtml(config.subtitle || '')}</span>
          </div>
          <div class="iaw-head-actions">
            <button class="iaw-icon-btn" type="button" data-role="min">—</button>
            <button class="iaw-icon-btn" type="button" data-role="close">×</button>
          </div>
        </div>
        <div class="iaw-body">
          <div class="iaw-tab-row"></div>
          <div class="iaw-desc"></div>
          <div class="iaw-shortcuts"></div>
          <div class="iaw-chat">
            <input type="text" data-role="chat-input" />
            <button class="iaw-primary" type="button" data-role="chat-send">Enviar</button>
          </div>
          <div class="iaw-exec">
            <button class="iaw-primary" type="button" data-role="exec">Executar análise</button>
            <span class="iaw-error" data-role="error"></span>
          </div>
          <div class="iaw-loading">Consultando IA, aguarde…</div>
          <div class="iaw-result"></div>
          <div class="iaw-actions">
            <button class="iaw-secondary" type="button" data-role="copy">Copiar</button>
            <button class="iaw-secondary" type="button" data-role="clear">Nova consulta</button>
          </div>
        </div>`;

      document.body.appendChild(fab);
      document.body.appendChild(panel);

      const tabRow = panel.querySelector('.iaw-tab-row');
      const descEl = panel.querySelector('.iaw-desc');
      const shortcutsEl = panel.querySelector('.iaw-shortcuts');
      const chatWrap = panel.querySelector('.iaw-chat');
      const chatInput = panel.querySelector('[data-role="chat-input"]');
      const chatSend = panel.querySelector('[data-role="chat-send"]');
      const execWrap = panel.querySelector('.iaw-exec');
      const execBtn = panel.querySelector('[data-role="exec"]');
      const errorEl = panel.querySelector('[data-role="error"]');
      const loadingEl = panel.querySelector('.iaw-loading');
      const resultEl = panel.querySelector('.iaw-result');
      const actionsEl = panel.querySelector('.iaw-actions');
      const copyBtn = panel.querySelector('[data-role="copy"]');
      const clearBtn = panel.querySelector('[data-role="clear"]');
      const minBtn = panel.querySelector('[data-role="min"]');
      const closeBtn = panel.querySelector('[data-role="close"]');

      chatInput.placeholder = config.chatPlaceholder || 'Digite sua pergunta';
      execBtn.textContent = config.execLabel || 'Executar análise';
      errorEl.textContent = config.emptyMessage || 'Dados insuficientes para usar a IA.';

      function open() {
        panel.classList.add('is-open');
        fab.classList.add('is-open');
      }

      function close() {
        panel.classList.remove('is-open');
        fab.classList.remove('is-open');
      }

      function getActionMeta(id) {
        return actions.find((item) => item.id === id) || { id, label: id, description: '' };
      }

      function setAction(id) {
        activeAction = id;
        Array.from(tabRow.children).forEach((btn) => btn.classList.toggle('active', btn.dataset.action === id));
        const meta = getActionMeta(id);
        descEl.textContent = meta.description || '';
        const isChat = id === 'chat';
        chatWrap.style.display = isChat ? 'flex' : 'none';
        execWrap.style.display = isChat ? 'none' : 'flex';
      }

      function showError(message, visible) {
        errorEl.textContent = message || config.emptyMessage || 'Dados insuficientes para usar a IA.';
        errorEl.style.display = visible ? 'inline' : 'none';
      }

      async function run(question) {
        try {
          if (typeof config.beforeRun === 'function') config.beforeRun(activeAction);
          if (typeof config.hasData === 'function' && !config.hasData()) {
            showError(config.emptyMessage || 'Dados insuficientes para usar a IA.', true);
            open();
            return;
          }
          showError('', false);
          open();
          loadingEl.style.display = 'block';
          resultEl.style.display = 'block';
          actionsEl.style.display = 'none';
          resultEl.textContent = '';
          const result = await config.onRun({ action: activeAction, question: question || '' });
          loadingEl.style.display = 'none';
          resultEl.innerHTML = renderMarkdownLite(result || 'Sem resposta da IA.');
          actionsEl.style.display = 'flex';
        } catch (error) {
          loadingEl.style.display = 'none';
          resultEl.style.display = 'block';
          resultEl.textContent = `Erro: ${error.message || error}`;
          actionsEl.style.display = 'flex';
        }
      }

      actions.forEach((action) => {
        const btn = createEl('button', 'iaw-tab', escapeHtml(action.label));
        btn.type = 'button';
        btn.dataset.action = action.id;
        btn.addEventListener('click', () => setAction(action.id));
        tabRow.appendChild(btn);
      });

      shortcuts.forEach((shortcut) => {
        const btn = createEl('button', 'iaw-chip', escapeHtml(shortcut.label));
        btn.type = 'button';
        btn.addEventListener('click', async () => {
          if (shortcut.action) setAction(shortcut.action);
          if (typeof shortcut.onClick === 'function') {
            await shortcut.onClick({ open, close, run, setAction });
            return;
          }
          await run(shortcut.question || '');
        });
        shortcutsEl.appendChild(btn);
      });

      fab.addEventListener('click', open);
      minBtn.addEventListener('click', close);
      closeBtn.addEventListener('click', close);
      execBtn.addEventListener('click', () => run(''));
      chatSend.addEventListener('click', () => {
        const question = chatInput.value.trim();
        if (!question) return;
        run(question);
        chatInput.value = '';
      });
      chatInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') chatSend.click();
      });
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(resultEl.innerText || resultEl.textContent || '');
        copyBtn.textContent = 'Copiado';
        setTimeout(() => { copyBtn.textContent = 'Copiar'; }, 1500);
      });
      clearBtn.addEventListener('click', () => {
        resultEl.style.display = 'none';
        actionsEl.style.display = 'none';
        loadingEl.style.display = 'none';
      });

      setAction(activeAction);

      return { open, close, run, setAction, elements: { fab, panel, resultEl } };
    }
  };
}());
