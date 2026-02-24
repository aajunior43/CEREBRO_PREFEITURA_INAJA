(function() {
  window.App = window.App || {};

  window.App.state = {
    rows: [],
    columns: [],
    filtered: [],
    sort: { key: null, dir: 1 },
    lastFile: null,
    filters: [],
    natureLabels: new Map(),
    selectedId: null,
    page: 1,
    pageSize: 50
  };

  window.App.elements = {
    file: document.getElementById("csvFile"),
    search: document.getElementById("search"),
    minValue: document.getElementById("minValue"),
    maxValue: document.getElementById("maxValue"),
    reset: document.getElementById("resetFilters"),
    printView: document.getElementById("printView"),
    toggleFilters: document.getElementById("toggleFilters"),
    totalValue: document.getElementById("totalValue"),
    totalRows: document.getElementById("totalRows"),
    avgValue: document.getElementById("avgValue"),
    maxValueStat: document.getElementById("maxValueStat"),
    printSelected: document.getElementById("printSelected"),
    exportCsv: document.getElementById("exportCsv"),
    printDate: document.getElementById("printDate"),
    table: document.getElementById("dataTable"),
    tableCount: document.getElementById("tableCount"),
    filterBoxes: Array.from(document.querySelectorAll(".filter-box")),
    filterChips: document.getElementById("filterChips"),
    printCard: document.getElementById("printCard"),
    prevPage: document.getElementById("prevPage"),
    nextPage: document.getElementById("nextPage"),
    pageInfo: document.getElementById("pageInfo"),
    pageSize: document.getElementById("pageSize")
  };
})();
