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
        // Ensure the current row is selected for print card rendering
        state.selectedId = row.__id;
        window.App.ui.renderPrintCard();
        if (window.App.ui.setPrintDate) window.App.ui.setPrintDate();

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
    const visibleColumns = window.App.ui.getVisibleColumns();
    elements.printCard.innerHTML = "";

    const header = document.createElement("div");
    header.className = "print-card-header";
    const title = document.createElement("h3");
    title.textContent = "Detalhamento da Despesa";
    header.appendChild(title);
    elements.printCard.appendChild(header);

    const grid = document.createElement("div");
    grid.className = "print-grid";

    visibleColumns.forEach((col) => {
      const wrapper = document.createElement("div");
      wrapper.className = "field-row";

      const lowerCol = col.toLowerCase();
      const isMoney = lowerCol.includes("valor") ||
        lowerCol.includes("saldo") ||
        lowerCol.includes("empenhado") ||
        lowerCol.includes("pago") ||
        lowerCol.includes("liquidado");

      const label = document.createElement("span");
      label.textContent = col;

      const value = document.createElement("strong");
      if (isMoney) {
        wrapper.classList.add("is-money");
        // Try to parse if not already a number? 
        // Assuming row[col] is the raw string from CSV usually, 
        // but for 'Saldo atual da despesa' we have __saldo.
        // The CSV might have pre-formatted strings for others.
        // Let's stick to simple display for now or use formatter if it matches known money column
        if (col === "Saldo atual da despesa") {
          value.textContent = formatter.format(row.__saldo || 0);
        } else {
          value.textContent = row[col] || "";
        }
      } else {
        value.textContent = row[col] || "";
      }

      wrapper.appendChild(label);
      wrapper.appendChild(value);
      grid.appendChild(wrapper);
    });

    elements.printCard.appendChild(grid);
  };

  window.App.ui.setPrintDate = function () {
    const el = document.getElementById("printDate");
    if (el) {
      const now = new Date();
      el.textContent = now.toLocaleDateString("pt-BR") + " " + now.toLocaleTimeString("pt-BR");
    }
  };
})();
