(function () {
  window.App = window.App || {};
  window.App.ui = {};

  let sortHandler = null;
  let selectHandler = null;

  window.App.ui.setSortHandler = function (fn) {
    sortHandler = fn;
  };

  window.App.ui.setSelectHandler = function (fn) {
    selectHandler = fn;
  };

  window.App.ui.getVisibleColumns = function () {
    // Ultra-compact view: only essential columns
    return [
      "Número da despesa",
      "Entidade",
      "Descrição do organograma",
      "Recurso",
      "Descrição do recurso",
      "Descrição da natureza de despesa",
      "Saldo atual da despesa"
    ];
  };

  window.App.ui.getDisplayValue = function (row, col) {
    const { formatter } = window.App.utils;

    if (col === "Saldo atual da despesa") {
      return formatter.format(row.__saldo || 0);
    }

    // Abbreviate entity to 3 letters
    if (col === "Entidade") {
      const entity = row[col] || "";
      // Extract first 3 letters (ignoring spaces)
      const letters = entity.replace(/[^A-Za-z]/g, '').substring(0, 3).toUpperCase();
      return letters || entity.substring(0, 3).toUpperCase();
    }

    // Show only first 5 digits of resource
    if (col === "Recurso") {
      const resource = row[col] || "";
      // Extract first 5 digits
      const digits = resource.replace(/[^0-9]/g, '').substring(0, 5);
      return digits || resource.substring(0, 5);
    }

    return row[col] || "";
  };

  // Modal Logic
  function showDetails(row) {
    const overlay = document.getElementById("modalOverlay");
    const content = document.getElementById("modalContent");
    const closeBtn = document.getElementById("closeModal");
    const printBtn = document.getElementById("printModalBtn");
    const { formatter } = window.App.utils;
    const { state } = window.App;

    if (!overlay || !content) return;

    content.innerHTML = "";

    // Show all columns
    state.columns.forEach(col => {
      const item = document.createElement("div");
      item.className = "detail-item";

      const label = document.createElement("span");
      label.className = "detail-label";
      label.textContent = col;

      const value = document.createElement("span");
      value.className = "detail-value";

      if (col === "Saldo atual da despesa") {
        value.textContent = formatter.format(row.__saldo || 0);
        value.classList.add("is-money");
      } else {
        value.textContent = row[col] || "-";
      }

      item.appendChild(label);
      item.appendChild(value);
      content.appendChild(item);
    });

    overlay.classList.remove("hidden");
    overlay.setAttribute("aria-hidden", "false");

    const close = () => {
      overlay.classList.add("hidden");
      overlay.setAttribute("aria-hidden", "true");
    };

    if (closeBtn) closeBtn.onclick = close;
    overlay.onclick = (e) => {
      if (e.target === overlay) close();
    };

    if (printBtn) {
      printBtn.onclick = () => {
        // Assegura que o ID selecionado no estado do App corresponda à dotação atual
        state.selectedId = row.__id;
        
        // Atualiza a tabela para refletir a seleção visual
        if (selectHandler) selectHandler(row.__id);
        
        // Renderiza o cartão de impressão institucional correspondente
        window.App.ui.renderPrintCard();
        if (window.App.ui.setPrintDate) window.App.ui.setPrintDate();

        // Adiciona classe de impressão e executa
        document.body.classList.add("print-selected");
        const cleanup = () => {
          document.body.classList.remove("print-selected");
          window.removeEventListener("afterprint", cleanup);
        };
        window.addEventListener("afterprint", cleanup);
        window.print();
      };
    }

    // Esc key
    const escHandler = function (e) {
      if (e.key === "Escape" && !overlay.classList.contains('hidden')) {
        close();
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  }

  window.App.ui.updateActiveChips = function (onRemove) {
    const { state, elements } = window.App;
    const chips = elements.filterChips;
    const reset = elements.reset;
    if (!chips) return;

    chips.innerHTML = '';
    let count = 0;

    const addChip = (label, type, filter) => {
      count++;
      const chip = document.createElement('div');
      chip.className = 'chip';
      chip.innerHTML = `<span>${label}</span><button title="Remover">×</button>`;
      chip.querySelector('button').addEventListener('click', () => onRemove(type, filter));
      chips.appendChild(chip);
    };

    if (elements.search && elements.search.value.trim())
      addChip(`🔍 "${elements.search.value.trim()}"`, 'search', null);
    if (elements.minValue && elements.minValue.value)
      addChip(`Mín: ${elements.minValue.value}`, 'min', null);
    if (elements.maxValue && elements.maxValue.value)
      addChip(`Máx: ${elements.maxValue.value}`, 'max', null);
    if (state.quickFilterPrefixes && state.quickFilterPrefixes.length)
      addChip(`Rápido: ${state.quickFilterLabel || state.quickFilterPrefixes.join(", ")}`, 'quick_filter', null);
    if (state.saldoCriticoAtivo)
      addChip(`Saldo crítico até ${state.saldoCriticoThreshold}`, 'saldo_critico', null);

    state.filters.forEach(filter => {
      if (filter.selected.size) {
        const vals = [...filter.selected].map(v => filter.labelFor ? filter.labelFor(v) : (v || '(Sem valor)')).join(', ');
        const short = vals.length > 40 ? vals.substring(0, 40) + '…' : vals;
        addChip(`${filter.box.querySelector('label').textContent.trim()}: ${short}`, 'filter_select', filter);
      }
      if (filter.query) {
        addChip(`${filter.box.querySelector('label').textContent.trim()} contém "${filter.query}"`, 'filter_query', filter);
      }
    });

    if (reset) reset.classList.toggle('is-hidden', count === 0);
  };

  window.App.ui.updateStats = function () {
    const { state, elements } = window.App;
    const { formatter, numberFormatter } = window.App.utils;

    const values = state.filtered.map((row) => row.__saldo || 0);
    const total = values.reduce((sum, value) => sum + value, 0);
    const avg = values.length ? total / values.length : 0;
    const max = values.length ? Math.max(...values) : 0;

    elements.totalValue.textContent = formatter.format(total);
    elements.totalRows.textContent = numberFormatter.format(state.filtered.length);
    elements.avgValue.textContent = formatter.format(avg);
    elements.maxValueStat.textContent = formatter.format(max);
    elements.tableCount.textContent = `${numberFormatter.format(state.filtered.length)} linhas`;
  };

  window.App.ui.updateTable = function () {
    const { state, elements } = window.App;
    const { formatter } = window.App.utils;

    const head = elements.table.querySelector("thead");
    const body = elements.table.querySelector("tbody");
    head.innerHTML = "";
    body.innerHTML = "";

    if (!state.columns.length) return;

    const visibleColumns = window.App.ui.getVisibleColumns();

    const headerRow = document.createElement("tr");
    visibleColumns.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      const isSorted = state.sort.key === col;
      if (isSorted) {
        th.classList.add(state.sort.dir === 1 ? "sorted-asc" : "sorted-desc");
        th.setAttribute("aria-sort", state.sort.dir === 1 ? "ascending" : "descending");
        th.title = state.sort.dir === 1
          ? `Ordenado por ${col} (crescente). Clique para inverter.`
          : `Ordenado por ${col} (decrescente). Clique para inverter.`;
      } else {
        th.setAttribute("aria-sort", "none");
        th.title = `Ordenar por ${col}`;
      }
      if (sortHandler) {
        th.addEventListener("click", () => sortHandler(col));
      }
      headerRow.appendChild(th);
    });
    head.appendChild(headerRow);

    const total = state.filtered.length;
    const pageCount = Math.max(1, Math.ceil(total / state.pageSize));
    if (state.page > pageCount) state.page = pageCount;

    const start = (state.page - 1) * state.pageSize;
    const end = start + state.pageSize;
    const rows = state.filtered.slice(start, end);

    rows.forEach((row) => {
      const tr = document.createElement("tr");

      // Add area color class based on function
      const funcao = row["Descrição da função"] || "";
      const areaInfo = window.App.utils.getAreaInfo(funcao);
      if (areaInfo && areaInfo.key) {
        tr.classList.add(`area-${areaInfo.key}`);
      }

      if (state.selectedId === row.__id) {
        tr.classList.add("table-row-selected");
      }
      // Highlight saldo crítico rows
      if (state.saldoCriticoThreshold !== undefined && row.__saldo <= state.saldoCriticoThreshold && row.__saldo >= 0) {
        tr.classList.add("saldo-critico");
      }
      tr.tabIndex = 0;
      tr.addEventListener("click", () => {
        if (selectHandler) selectHandler(row.__id);
        showDetails(row);
      });
      tr.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          if (selectHandler) selectHandler(row.__id);
          showDetails(row);
        }
      });
      visibleColumns.forEach((col) => {
        const td = document.createElement("td");
        const displayValue = window.App.ui.getDisplayValue(row, col);

        // Add data-label for card layout
        td.setAttribute("data-label", col);

        // Add badge for function column
        if (col === "Descrição da função" && funcao) {
          const badge = document.createElement("span");
          badge.className = `area-badge ${areaInfo.key}`;
          badge.textContent = funcao;
          td.appendChild(badge);
        } else {
          td.textContent = displayValue;
        }

        if (col === "Saldo atual da despesa") {
          td.classList.add("col-saldo");
          td.title = displayValue;
        } else if (col === "Entidade") {
          td.title = row[col] || "";
        } else {
          td.title = displayValue;
        }
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });

    if (elements.pageInfo) {
      elements.pageInfo.textContent = `Página ${state.page} de ${pageCount}`;
    }
    if (elements.prevPage) elements.prevPage.disabled = state.page <= 1;
    if (elements.nextPage) elements.nextPage.disabled = state.page >= pageCount;
  };

  window.App.ui.renderFilterOptions = function (filter) {
    const { normalizeText } = window.App.utils;
    const query = normalizeText(filter.search.value.trim());
    filter.optionsEl.innerHTML = "";

    if (!filter.values.length) return;

    // Add cascade indicator if active
    if (filter.cascadeActive && filter.cascadeParent) {
      const indicator = document.createElement("div");
      indicator.className = "cascade-indicator";
      indicator.innerHTML = `<span class="cascade-icon">🔗</span> Filtrado por: ${filter.cascadeParent.replace("Descrição da ", "").replace("Descrição do ", "")}`;
      filter.optionsEl.appendChild(indicator);
    }

    const availableOptions = filter.availableOptions || new Set(filter.values);
    let availableCount = 0;
    let totalCount = 0;

    filter.values.forEach((value, optionIndex) => {
      const labelText = filter.labelFor ? filter.labelFor(value) : (value || "(Sem valor)");
      if (query && !normalizeText(labelText).includes(query)) return;

      totalCount++;
      const isAvailable = availableOptions.has(value);
      if (isAvailable) availableCount++;

      const optionId = `filter-${filter.index}-${optionIndex}`;
      const label = document.createElement("label");
      label.className = "filter-option" + (isAvailable ? "" : " unavailable");

      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = value;
      input.id = optionId;
      input.checked = filter.selected.has(value);
      input.disabled = !isAvailable && !filter.selected.has(value);

      const span = document.createElement("span");
      span.textContent = labelText;

      label.appendChild(input);
      label.appendChild(span);
      filter.optionsEl.appendChild(label);
    });

    // Add availability counter
    if (availableCount < totalCount) {
      const counter = document.createElement("div");
      counter.className = "filter-counter";
      counter.textContent = `${availableCount} de ${totalCount} disponíveis`;
      filter.optionsEl.insertBefore(counter, filter.optionsEl.firstChild);
    }
  };

  window.App.ui.renderPrintCard = function () {
    const { state, elements } = window.App;
    const { formatter } = window.App.utils;

    if (!elements.printCard) return;
    const row = state.rows.find((item) => item.__id === state.selectedId);
    if (!row) return;

    // Build a doc ID from hash of numero+natureza
    const numDespesa = row['Número da despesa'] || row['Numero da despesa'] || '-';
    const natureza   = row['Natureza de Despesa'] || '';
    const docId = `DOT-${numDespesa.replace(/\D/g, '').padStart(5,'0')}-${new Date().getFullYear()}`;

    const areaInfo = window.App.utils.getAreaInfo(row['Descrição da função'] || '');

    // All printable columns (excluding internal __ keys and virtual group cols)
    const skipCols = new Set(['Tipo de Gasto','Tipo de Despesa','Origem do Recurso','Secretaria/Órgão','Área de Atuação']);
    const printCols = (state.columns || []).filter(c => !c.startsWith('__') && !skipCols.has(c) && c !== 'Saldo atual da despesa');

    // Group into two columns for layout
    const half = Math.ceil(printCols.length / 2);
    const col1 = printCols.slice(0, half);
    const col2 = printCols.slice(half);

    function fieldRow(col) {
      let val = row[col] || '—';
      return `<div class="pc-field">
        <span class="pc-label">${col}</span>
        <strong class="pc-value">${val}</strong>
      </div>`;
    }

    elements.printCard.innerHTML = `
      <div class="pc-wrap">

        <!-- Cabeçalho institucional -->
        <div class="pc-header">
          <div class="pc-header-logo">
            <img src="/static/img/brasao.png" alt="Brasão" />
          </div>
          <div class="pc-header-text">
            <div class="pc-header-title">Prefeitura Municipal de Inajá</div>
            <div class="pc-header-sub">Estado de Pernambuco — Secretaria de Finanças</div>
            <div class="pc-header-doc">Dotação Orçamentária — Ficha de Detalhamento</div>
          </div>
          <div class="pc-header-id">
            <div class="pc-id-label">Documento</div>
            <div class="pc-id-value">${docId}</div>
          </div>
        </div>

        <!-- Destaque financeiro -->
        <div class="pc-saldo-box">
          <div class="pc-saldo-left">
            <span class="pc-saldo-label">Saldo Atual da Despesa</span>
            <span class="pc-saldo-num">${formatter.format(row.__saldo || 0)}</span>
          </div>
          <div class="pc-saldo-right">
            <div class="pc-saldo-meta">
              <span class="pc-meta-label">Nº Despesa</span>
              <span class="pc-meta-val">${numDespesa}</span>
            </div>
            <div class="pc-saldo-meta">
              <span class="pc-meta-label">Natureza</span>
              <span class="pc-meta-val">${natureza}</span>
            </div>
            <div class="pc-saldo-meta">
              <span class="pc-meta-label">Área</span>
              <span class="pc-meta-val pc-area">${areaInfo.label || 'Outros'}</span>
            </div>
          </div>
        </div>

        <!-- Divisor -->
        <div class="pc-section-title">Dados da Dotação</div>

        <!-- Grid de campos em duas colunas -->
        <div class="pc-grid">
          <div class="pc-col">
            ${col1.map(fieldRow).join('')}
          </div>
          <div class="pc-col">
            ${col2.map(fieldRow).join('')}
          </div>
        </div>

        <!-- Classificação orçamentária -->
        <div class="pc-section-title">Classificação</div>
        <div class="pc-classif">
          <div class="pc-classif-row">
            <span class="pc-label">Tipo de Gasto</span>
            <strong>${row['Tipo de Gasto'] || '—'}</strong>
          </div>
          <div class="pc-classif-row">
            <span class="pc-label">Tipo de Despesa</span>
            <strong>${row['Tipo de Despesa'] || '—'}</strong>
          </div>
          <div class="pc-classif-row">
            <span class="pc-label">Origem do Recurso</span>
            <strong>${row['Origem do Recurso'] || '—'}</strong>
          </div>
          <div class="pc-classif-row">
            <span class="pc-label">Secretaria/Órgão</span>
            <strong>${row['Secretaria/Órgão'] || '—'}</strong>
          </div>
          <div class="pc-classif-row">
            <span class="pc-label">Área de Atuação</span>
            <strong>${row['Área de Atuação'] || '—'}</strong>
          </div>
        </div>

        <!-- Rodapé -->
        <div class="pc-footer">
          <div class="pc-footer-left">
            <div>Prefeitura Municipal de Inajá — PE</div>
            <div>Documento gerado pelo Sistema CÉREBRO</div>
          </div>
          <div class="pc-footer-right">
            <div id="pc-print-date"></div>
            <div class="pc-doc-ref">${docId}</div>
          </div>
        </div>

      </div>
    `;

    // Set date inside the card
    const dateEl = elements.printCard.querySelector('#pc-print-date');
    if (dateEl) {
      const now = new Date();
      dateEl.textContent = 'Emitido em ' + now.toLocaleDateString('pt-BR') + ' às ' + now.toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'});
    }
  };


  window.App.ui.setPrintDate = function () {
    const el = document.getElementById("printDate");
    if (el) {
      const now = new Date();
      el.textContent = now.toLocaleDateString("pt-BR") + " " + now.toLocaleTimeString("pt-BR");
    }
  };
})();
