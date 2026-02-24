(function () {
  window.App = window.App || {};
  window.App.logic = {};

  // Cascade hierarchy: parent column -> child columns
  const CASCADE_HIERARCHY = {
    "Descrição da função": ["Descrição do programa", "Descrição da ação"],
    "Descrição do programa": ["Descrição da ação"]
  };

  window.App.logic.sortBy = function (column) {
    const { state } = window.App;
    const { updateTable } = window.App.ui;

    if (state.sort.key === column) {
      state.sort.dir *= -1;
    } else {
      state.sort.key = column;
      state.sort.dir = 1;
    }

    const dir = state.sort.dir;
    state.filtered.sort((a, b) => {
      const av = a[column] || "";
      const bv = b[column] || "";
      if (column === "Saldo atual da despesa") {
        return dir * ((a.__saldo || 0) - (b.__saldo || 0));
      }
      return dir * av.localeCompare(bv, "pt-BR", { numeric: true });
    });

    updateTable();
  };

  // Calculate available options for each filter based on current filtered data
  function getAvailableOptions(excludeFilter = null) {
    const { state, elements } = window.App;
    const { normalizeText } = window.App.utils;

    const query = normalizeText(elements.search.value.trim());
    const min = Number.parseFloat(elements.minValue.value) || 0;
    const max = Number.parseFloat(elements.maxValue.value) || Infinity;

    // Filter data excluding the filter being updated
    const tempFiltered = state.rows.filter((row) => {
      for (const filter of state.filters) {
        if (filter === excludeFilter) continue; // Skip the filter being updated
        if (filter.box.classList.contains("disabled")) continue;
        const value = row[filter.column] || "";
        if (filter.selected.size && !filter.selected.has(value)) return false;
      }
      if (row.__saldo < min || row.__saldo > max) return false;
      if (!query) return true;
      const hay = normalizeText(state.columns.map((col) => row[col]).join(" "));
      return hay.includes(query);
    });

    // Calculate available values for each filter
    const availableByFilter = new Map();
    state.filters.forEach((filter) => {
      const available = new Set();
      tempFiltered.forEach((row) => {
        const value = row[filter.column] || "";
        if (value) available.add(value);
      });
      availableByFilter.set(filter, available);
    });

    return availableByFilter;
  }

  window.App.logic.applyFilters = function () {
    const { state, elements } = window.App;
    const { normalizeText } = window.App.utils;
    const { updateStats, updateTable, updateActiveChips, renderFilterOptions } = window.App.ui;

    const query = normalizeText(elements.search.value.trim());
    const min = Number.parseFloat(elements.minValue.value) || 0;
    const max = Number.parseFloat(elements.maxValue.value) || Infinity;

    state.filtered = state.rows.filter((row) => {
      for (const filter of state.filters) {
        if (filter.box.classList.contains("disabled")) continue;
        const value = row[filter.column] || "";
        if (filter.selected.size && !filter.selected.has(value)) return false;
        if (filter.query) {
          const labelText = filter.labelFor ? filter.labelFor(value) : value;
          if (!normalizeText(labelText).includes(filter.query)) return false;
        }
      }
      if (row.__saldo < min || row.__saldo > max) return false;
      if (!query) return true;
      const hay = normalizeText(state.columns.map((col) => row[col]).join(" "));
      return hay.includes(query);
    });

    // Update available options for all filters
    const availableByFilter = getAvailableOptions();
    state.filters.forEach((filter) => {
      filter.availableOptions = availableByFilter.get(filter);
      renderFilterOptions(filter);
    });

    state.page = 1;
    updateStats();
    updateTable();
    updateActiveChips(handleChipRemove);
  };

  function handleChipRemove(type, filter) {
    const { elements } = window.App;
    const { renderFilterOptions } = window.App.ui;
    const { applyFilters } = window.App.logic;

    if (type === 'search') {
      elements.search.value = "";
    } else if (type === 'min') {
      elements.minValue.value = "";
    } else if (type === 'max') {
      elements.maxValue.value = "";
    } else if (type === 'filter_select') {
      filter.selected.clear();
      renderFilterOptions(filter);
    } else if (type === 'filter_query') {
      filter.search.value = "";
      filter.query = "";
      filter.rawQuery = "";
      renderFilterOptions(filter);
    }
    applyFilters();
  }

  window.App.logic.resetFilters = function () {
    const { state, elements } = window.App;
    const { renderFilterOptions } = window.App.ui;
    const { applyFilters } = window.App.logic;

    elements.search.value = "";
    elements.minValue.value = "";
    elements.maxValue.value = "";
    state.filters.forEach((filter) => {
      filter.search.value = "";
      filter.query = "";
      filter.rawQuery = "";
      filter.selected.clear();
      renderFilterOptions(filter);
    });
    applyFilters();
  };

  // Update cascade filter options based on parent selections
  window.App.logic.updateCascadeFilters = function () {
    const { state } = window.App;
    const { renderFilterOptions } = window.App.ui;

    state.filters.forEach((childFilter) => {
      // Check if this filter has a parent in the cascade hierarchy
      let parentColumn = null;
      for (const [parent, children] of Object.entries(CASCADE_HIERARCHY)) {
        if (children.includes(childFilter.column)) {
          parentColumn = parent;
          break;
        }
      }

      if (!parentColumn) return; // No parent, skip cascade

      // Find the parent filter
      const parentFilter = state.filters.find(f => f.column === parentColumn);
      if (!parentFilter || parentFilter.selected.size === 0) {
        // No parent selections, show all options
        const values = new Set();
        state.rows.forEach((row) => {
          values.add(row[childFilter.column] || "");
        });
        childFilter.values = Array.from(values).sort((a, b) =>
          a.localeCompare(b, "pt-BR", { numeric: true })
        );
        childFilter.cascadeActive = false;
      } else {
        // Parent has selections, filter child options
        const values = new Set();
        state.rows.forEach((row) => {
          const parentValue = row[parentColumn] || "";
          if (parentFilter.selected.has(parentValue)) {
            values.add(row[childFilter.column] || "");
          }
        });
        childFilter.values = Array.from(values).sort((a, b) =>
          a.localeCompare(b, "pt-BR", { numeric: true })
        );
        childFilter.cascadeActive = true;
        childFilter.cascadeParent = parentFilter.column;
      }

      // Clear selections that are no longer valid
      const validValues = new Set(childFilter.values);
      const toRemove = [];
      childFilter.selected.forEach(value => {
        if (!validValues.has(value)) {
          toRemove.push(value);
        }
      });
      toRemove.forEach(value => childFilter.selected.delete(value));

      renderFilterOptions(childFilter);
    });
  };

  window.App.logic.loadCSV = function (text) {
    const { state } = window.App;
    const { detectDelimiter, parseCSV } = window.App.csv;
    const { parseCurrency } = window.App.utils;
    const { renderFilterOptions } = window.App.ui;
    const { applyFilters } = window.App.logic;

    const delimiter = detectDelimiter(text);
    const rows = parseCSV(text, delimiter).filter((row) => row.some((cell) => cell.trim() !== ""));
    if (!rows.length) return;

    const header = rows[0];

    // Add virtual columns
    state.columns = [...header, "Tipo de Gasto", "Tipo de Despesa", "Origem do Recurso", "Secretaria/Órgão", "Área de Atuação"];

    state.rows = rows.slice(1).map((values) => {
      const row = {};
      header.forEach((col, index) => {
        row[col] = values[index] || "";
      });
      row.__id = Math.random().toString(36).slice(2);
      row.__saldo = parseCurrency(row["Saldo atual da despesa"]);

      // Calculate virtual columns
      const { getTipoGasto, getTipoDespesa, getOrigemRecurso, getSecretaria, getAreaAtuacao } = window.App.utils;
      row["Tipo de Gasto"] = getTipoGasto(row["Natureza de Despesa"]);
      row["Tipo de Despesa"] = getTipoDespesa(row["Natureza de Despesa"]);
      row["Origem do Recurso"] = getOrigemRecurso(row["Descrição do recurso"]);
      row["Secretaria/Órgão"] = getSecretaria(row["Descrição do organograma"]);
      row["Área de Atuação"] = getAreaAtuacao(row["Descrição da função"]);

      return row;
    });

    state.natureLabels = new Map();
    state.rows.forEach((row) => {
      const code = row["Natureza de Despesa"] || "";
      const desc = row["Descrição da natureza de despesa"] || "";
      if (!code) return;
      const label = desc ? `${code} - ${desc}` : code;
      state.natureLabels.set(code, label);
    });

    const columnSet = new Set(state.columns);
    state.filters.forEach((filter) => {
      const available = columnSet.has(filter.column);
      filter.box.classList.toggle("disabled", !available);
      if (!available) {
        filter.values = [];
        filter.selected.clear();
        filter.optionsEl.innerHTML = "";
        return;
      }
      const values = new Set();
      state.rows.forEach((row) => {
        values.add(row[filter.column] || "");
      });
      filter.values = Array.from(values).sort((a, b) =>
        a.localeCompare(b, "pt-BR", { numeric: true })
      );
      if (filter.column === "Natureza de Despesa") {
        filter.labelFor = (value) => state.natureLabels.get(value) || value || "(Sem valor)";
      } else {
        filter.labelFor = null;
      }
      filter.selected.clear();
      filter.search.value = "";
      filter.query = "";
      renderFilterOptions(filter);
    });

    applyFilters();
  };

  window.App.logic.exportVisibleCSV = function () {
    const { state } = window.App;
    const { getVisibleColumns, getDisplayValue } = window.App.ui;
    if (!state.columns.length) return;
    const visibleColumns = getVisibleColumns();
    const total = state.filtered.length;
    const pageCount = Math.max(1, Math.ceil(total / state.pageSize));
    if (state.page > pageCount) state.page = pageCount;
    const start = (state.page - 1) * state.pageSize;
    const end = start + state.pageSize;
    const rows = state.filtered.slice(start, end);

    const escapeValue = (value) => {
      const text = value == null ? "" : String(value);
      const needsQuote = /[;"\r\n]/.test(text);
      const escaped = text.replace(/"/g, '""');
      return needsQuote ? `"${escaped}"` : escaped;
    };

    const headerLine = visibleColumns.map(escapeValue).join(";");
    const lines = rows.map((row) =>
      visibleColumns.map((col) => escapeValue(getDisplayValue(row, col))).join(";")
    );
    const content = [`\ufeff${headerLine}`, ...lines].join("\r\n");
    const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 10);
    link.href = url;
    link.download = `despesas-visiveis-${stamp}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  window.App.logic.initFilters = function () {
    const { state, elements } = window.App;
    const { normalizeText } = window.App.utils;
    const { renderFilterOptions } = window.App.ui;
    const { applyFilters } = window.App.logic;

    state.filters = elements.filterBoxes.map((box, index) => {
      return {
        box,
        index,
        column: box.dataset.column || "",
        search: box.querySelector(".filter-search"),
        optionsEl: box.querySelector(".filter-options"),
        toggle: box.querySelector(".filter-toggle"),
        selected: new Set(),
        values: [],
        query: "",
        rawQuery: "",
        labelFor: null
      };
    });

    state.filters.forEach((filter) => {
      if (filter.toggle) {
        filter.toggle.addEventListener("click", () => {
          filter.box.classList.toggle("collapsed");
          const expanded = !filter.box.classList.contains("collapsed");
          filter.toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
          filter.toggle.textContent = expanded ? "Fechar" : "Abrir";
        });
      }
      filter.search.addEventListener("input", () => {
        filter.rawQuery = filter.search.value.trim();
        filter.query = normalizeText(filter.rawQuery);
        renderFilterOptions(filter);
        applyFilters();
      });

      filter.optionsEl.addEventListener("change", (event) => {
        const target = event.target;
        if (!target || target.type !== "checkbox") return;
        const value = target.value;
        if (target.checked) {
          filter.selected.add(value);
        } else {
          filter.selected.delete(value);
        }

        // Update cascade filters if this filter is a parent
        const { updateCascadeFilters } = window.App.logic;
        if (CASCADE_HIERARCHY[filter.column]) {
          updateCascadeFilters();
        }

        applyFilters();
      });

      const buttons = Array.from(filter.box.querySelectorAll("[data-action]"));
      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          const type = button.dataset.action;
          if (type === "all") {
            filter.selected = new Set(filter.values);
          } else {
            filter.selected.clear();
          }
          renderFilterOptions(filter);

          // Update cascade filters if this filter is a parent
          const { updateCascadeFilters } = window.App.logic;
          if (CASCADE_HIERARCHY[filter.column]) {
            updateCascadeFilters();
          }

          applyFilters();
        });
      });
    });
  };
})();
