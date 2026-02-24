(function() {
  window.App = window.App || {};
  window.App.csv = {};

  window.App.csv.parseCSV = function(text, delimiter) {
    const rows = [];
    let current = "";
    let inQuotes = false;
    let row = [];

    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      if (char === '"') {
        if (inQuotes && text[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
        continue;
      }

      if (!inQuotes && char === delimiter) {
        row.push(current);
        current = "";
        continue;
      }

      if (!inQuotes && (char === "\n" || char === "\r")) {
        if (current.length > 0 || row.length > 0) {
          row.push(current);
          rows.push(row);
          row = [];
          current = "";
        }
        if (char === "\r" && text[i + 1] === "\n") {
          i++;
        }
        continue;
      }

      current += char;
    }

    if (current.length > 0 || row.length > 0) {
      row.push(current);
      rows.push(row);
    }

    return rows;
  };

  window.App.csv.detectDelimiter = function(text) {
    const firstLine = text.split(/\r?\n/)[0] || "";
    const candidates = [";", ",", "\t"];
    let best = ";";
    let bestCount = -1;
    candidates.forEach((char) => {
      const count = firstLine.split(char).length - 1;
      if (count > bestCount) {
        bestCount = count;
        best = char;
      }
    });
    return best;
  };
})();