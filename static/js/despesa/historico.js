(function () {
  /* ────────────────────────────────────────────────────────
     Módulo Histórico – salva e carrega CSVs no banco SQLite
  ──────────────────────────────────────────────────────── */

  const BASE = '';

  // ── Salvar no banco ──────────────────────────────────────
  window.DespesaHistorico = {};

  window.DespesaHistorico.salvar = async function (periodo, descricao, arquivo) {
    const { state } = window.App;
    if (!state.rows || !state.rows.length) {
      alert('Nenhum dado carregado para salvar.');
      return;
    }

    const colunas = state.columns.filter(c => !c.startsWith('__'));
    // Serializa linhas excluindo chaves internas (__id, __saldo, colunas virtuais)
    const virtualCols = ['Tipo de Gasto', 'Tipo de Despesa', 'Origem do Recurso', 'Secretaria/Órgão', 'Área de Atuação'];
    const colsParaSalvar = colunas.filter(c => !virtualCols.includes(c));

    const linhas = state.rows.map(row => {
      const obj = {};
      colsParaSalvar.forEach(col => { obj[col] = row[col] || ''; });
      return obj;
    });

    try {
      const resp = await fetch('/api/despesas/importar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ periodo, descricao, arquivo, colunas: colsParaSalvar, linhas })
      });
      let data;
      const text = await resp.text();
      try {
        data = JSON.parse(text);
      } catch (_) {
        throw new Error('Servidor retornou resposta inválida (não-JSON). Verifique se o servidor foi reiniciado após as últimas alterações.');
      }
      if (!resp.ok) throw new Error(data.error || 'Erro ao salvar');
      return data;
    } catch (e) {
      throw e;
    }
  };

  // ── Listar importações ───────────────────────────────────
  window.DespesaHistorico.listar = async function () {
    const resp = await fetch('/api/despesas/importacoes');
    if (!resp.ok) throw new Error('Erro ao listar importações');
    return resp.json();
  };

  // ── Carregar importação ──────────────────────────────────
  window.DespesaHistorico.carregar = async function (id) {
    const resp = await fetch(`/api/despesas/importacoes/${id}`);
    if (!resp.ok) throw new Error('Importação não encontrada');
    const { importacao, linhas } = await resp.json();

    const { state } = window.App;
    const { parseCurrency, getTipoGasto, getTipoDespesa, getOrigemRecurso, getSecretaria, getAreaAtuacao } = window.App.utils;
    const { renderFilterOptions } = window.App.ui;
    const { applyFilters } = window.App.logic;

    const header = importacao.colunas;
    state.columns = [...header, 'Tipo de Gasto', 'Tipo de Despesa', 'Origem do Recurso', 'Secretaria/Órgão', 'Área de Atuação'];

    state.rows = linhas.map(row => {
      const r = Object.assign({}, row);
      r.__id = Math.random().toString(36).slice(2);
      r.__saldo = parseCurrency(r['Saldo atual da despesa']);
      r['Tipo de Gasto']      = getTipoGasto(r['Natureza de Despesa']);
      r['Tipo de Despesa']    = getTipoDespesa(r['Natureza de Despesa']);
      r['Origem do Recurso']  = getOrigemRecurso(r['Descrição do recurso']);
      r['Secretaria/Órgão']   = getSecretaria(r['Descrição do organograma']);
      r['Área de Atuação']    = getAreaAtuacao(r['Descrição da função']);
      return r;
    });

    state.natureLabels = new Map();
    state.rows.forEach(row => {
      const code = row['Natureza de Despesa'] || '';
      const desc = row['Descrição da natureza de despesa'] || '';
      if (code) state.natureLabels.set(code, desc ? `${code} - ${desc}` : code);
    });

    const colSet = new Set(state.columns);
    state.filters.forEach(filter => {
      const available = colSet.has(filter.column);
      filter.box.classList.toggle('disabled', !available);
      if (!available) { filter.values = []; filter.selected.clear(); filter.optionsEl.innerHTML = ''; return; }
      const vals = new Set();
      state.rows.forEach(row => vals.add(row[filter.column] || ''));
      filter.values = Array.from(vals).sort((a, b) => a.localeCompare(b, 'pt-BR', { numeric: true }));
      if (filter.column === 'Natureza de Despesa') {
        filter.labelFor = value => state.natureLabels.get(value) || value || '(Sem valor)';
      } else {
        filter.labelFor = null;
      }
      filter.selected.clear();
      filter.search.value = '';
      filter.query = '';
      renderFilterOptions(filter);
    });

    applyFilters();
    return importacao;
  };

  // ── Excluir importação ───────────────────────────────────
  window.DespesaHistorico.excluir = async function (id) {
    const resp = await fetch(`/api/despesas/importacoes/${id}`, { method: 'DELETE' });
    if (!resp.ok) throw new Error('Erro ao excluir');
    return resp.json();
  };

  // ── Renderizar painel de histórico ───────────────────────
  window.DespesaHistorico.renderPainel = async function () {
    const painel = document.getElementById('historico-painel');
    const lista  = document.getElementById('historico-lista');
    if (!painel || !lista) return;

    lista.innerHTML = '<div class="hist-loading">Carregando…</div>';

    let importacoes = [];
    try {
      importacoes = await window.DespesaHistorico.listar();
    } catch (e) {
      lista.innerHTML = '<div class="hist-empty">Erro ao carregar histórico.</div>';
      return;
    }

    if (!importacoes.length) {
      lista.innerHTML = '<div class="hist-empty">Nenhuma importação salva ainda.<br>Faça upload de um CSV e salve no banco.</div>';
      return;
    }

    lista.innerHTML = '';
    importacoes.forEach(imp => {
      const item = document.createElement('div');
      item.className = 'hist-item';
      item.innerHTML = `
        <div class="hist-item-info">
          <span class="hist-periodo">${escHtml(imp.periodo)}</span>
          ${imp.descricao ? `<span class="hist-desc">${escHtml(imp.descricao)}</span>` : ''}
          <span class="hist-meta">${imp.total_rows} linhas · ${formatDate(imp.importado_em)}</span>
          ${imp.arquivo ? `<span class="hist-arquivo">${escHtml(imp.arquivo)}</span>` : ''}
        </div>
        <div class="hist-item-actions">
          <button class="hist-btn hist-btn-load" data-id="${imp.id}" title="Carregar dados">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Carregar
          </button>
          <button class="hist-btn hist-btn-del" data-id="${imp.id}" title="Excluir">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
          </button>
        </div>
      `;
      lista.appendChild(item);
    });

    // bind events
    lista.querySelectorAll('.hist-btn-load').forEach(btn => {
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        btn.textContent = '…';
        try {
          const imp = await window.DespesaHistorico.carregar(Number(btn.dataset.id));
          // Highlight active
          lista.querySelectorAll('.hist-item').forEach(el => el.classList.remove('active'));
          btn.closest('.hist-item').classList.add('active');
          // Show period label in hero
          const label = document.getElementById('periodo-ativo');
          if (label) label.textContent = `📂 ${imp.periodo}${imp.descricao ? ' – ' + imp.descricao : ''}`;
        } catch (e) {
          alert('Erro ao carregar: ' + e.message);
        } finally {
          btn.disabled = false;
          btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Carregar`;
        }
      });
    });

    lista.querySelectorAll('.hist-btn-del').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (!confirm('Excluir esta importação? Esta ação não pode ser desfeita.')) return;
        try {
          await window.DespesaHistorico.excluir(Number(btn.dataset.id));
          btn.closest('.hist-item').remove();
          if (!lista.querySelector('.hist-item')) {
            lista.innerHTML = '<div class="hist-empty">Nenhuma importação salva ainda.</div>';
          }
        } catch (e) {
          alert('Erro ao excluir: ' + e.message);
        }
      });
    });
  };

  function escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function formatDate(dt) {
    if (!dt) return '';
    const d = new Date(dt.replace(' ', 'T'));
    return isNaN(d) ? dt : d.toLocaleString('pt-BR', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' });
  }
})();
