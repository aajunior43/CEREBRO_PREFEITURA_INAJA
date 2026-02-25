(function () {
  const { state, elements } = window.App;
  const { decodeBuffer } = window.App.utils;
  const { loadCSV, applyFilters, resetFilters, initFilters, sortBy, exportVisibleCSV } = window.App.logic;
  const UI = window.App.ui;

  UI.setSortHandler(sortBy);
  UI.setSelectHandler((id) => {
    state.selectedId = id;
    UI.updateTable();
  });

  function handleFile(file) {
    if (!file) return;
    state.lastFile = file;
    state.selectedId = null;
    state.page = 1;
    const reader = new FileReader();
    reader.onload = (event) => {
      const buffer = event.target.result;
      const text = decodeBuffer(buffer);
      loadCSV(text);
    };
    reader.readAsArrayBuffer(file);
  }

  ["search", "minValue", "maxValue"].forEach((id) => {
    if (elements[id]) {
      elements[id].addEventListener("input", applyFilters);
      elements[id].addEventListener("change", applyFilters);
    }
  });

  if (elements.numDespesa) {
    elements.numDespesa.addEventListener("input", () => {
      const { normalizeText } = window.App.utils;
      window.App.state.numDespesaQuery = normalizeText(elements.numDespesa.value.trim());
      applyFilters();
    });
  }

  if (elements.reset) elements.reset.addEventListener("click", resetFilters);

  if (elements.printView) {
    elements.printView.addEventListener("click", () => {
      UI.setPrintDate();
      window.print();
    });
  }

  if (elements.toggleFilters) {
    elements.toggleFilters.addEventListener("click", () => {
      const filtersSection = elements.toggleFilters.closest(".filters");
      if (!filtersSection) return;
      const isCollapsed = filtersSection.classList.toggle("collapsed");
      elements.toggleFilters.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      elements.toggleFilters.textContent = isCollapsed ? "Expandir filtros" : "Recolher filtros";
    });
  }

  if (elements.printSelected) {
    elements.printSelected.addEventListener("click", () => {
      if (!state.selectedId) return;
      UI.renderPrintCard();
      UI.setPrintDate();
      document.body.classList.add("print-selected");
      const cleanup = () => {
        document.body.classList.remove("print-selected");
        window.removeEventListener("afterprint", cleanup);
      };
      window.addEventListener("afterprint", cleanup);
      window.print();
    });
  }

  if (elements.exportCsv) {
    elements.exportCsv.addEventListener("click", exportVisibleCSV);
  }

  if (elements.file) {
    elements.file.addEventListener("change", (event) => {
      const file = event.target.files[0];
      handleFile(file);
    });
  }

  if (elements.pageSize) {
    const initial = Number.parseInt(elements.pageSize.value, 10);
    if (!Number.isNaN(initial)) {
      state.pageSize = initial;
    }
    elements.pageSize.addEventListener("change", () => {
      const value = Number.parseInt(elements.pageSize.value, 10);
      if (!Number.isNaN(value)) {
        state.pageSize = value;
        state.page = 1;
        UI.updateTable();
      }
    });
  }

  if (elements.prevPage) {
    elements.prevPage.addEventListener("click", () => {
      state.page = Math.max(1, state.page - 1);
      UI.updateTable();
    });
  }

  if (elements.nextPage) {
    elements.nextPage.addEventListener("click", () => {
      state.page += 1;
      UI.updateTable();
    });
  }

  // View mode toggle (List/Grid)
  const viewListBtn = document.getElementById("viewList");
  const viewGridBtn = document.getElementById("viewGrid");
  const tableWrap = document.querySelector(".table-wrap");

  function setViewMode(mode) {
    const isGrid = mode === "grid";

    if (isGrid) {
      tableWrap.classList.add("grid-mode");
      viewGridBtn.classList.add("active");
      viewListBtn.classList.remove("active");
    } else {
      tableWrap.classList.remove("grid-mode");
      viewListBtn.classList.add("active");
      viewGridBtn.classList.remove("active");
    }

    // Save preference
    localStorage.setItem("viewMode", mode);
  }

  if (viewListBtn && viewGridBtn && tableWrap) {
    viewListBtn.addEventListener("click", () => setViewMode("list"));
    viewGridBtn.addEventListener("click", () => setViewMode("grid"));

    // Load saved preference
    const savedMode = localStorage.getItem("viewMode") || "list";
    setViewMode(savedMode);
  }

  const accordionQuery = window.matchMedia("(max-width: 900px)");
  function updateAccordionDefaults() {
    state.filters.forEach((filter) => {
      if (!filter.toggle) return;
      if (accordionQuery.matches) {
        filter.box.classList.add("collapsed");
        filter.toggle.setAttribute("aria-expanded", "false");
        filter.toggle.textContent = "Abrir";
      } else {
        filter.box.classList.remove("collapsed");
        filter.toggle.setAttribute("aria-expanded", "true");
        filter.toggle.textContent = "Fechar";
      }
    });
  }

  initFilters();
  updateAccordionDefaults();
  accordionQuery.addEventListener("change", updateAccordionDefaults);

  async function autoLoadCSV() {
    const candidates = [
      "/static/dados/Relação de Despesas.csv",
      "/static/dados/dados.csv",
      "/static/dados/data.csv"
    ];

    for (const path of candidates) {
      try {
        const response = await fetch(path);
        if (response.ok) {
          const buffer = await response.arrayBuffer();
          const text = decodeBuffer(buffer);
          loadCSV(text);
          break;
        }
      } catch (e) {
        console.warn(`Could not load ${path} (likely due to file:// protocol restrictions or file not found)`, e);
      }
    }
  }

  autoLoadCSV();
})();
