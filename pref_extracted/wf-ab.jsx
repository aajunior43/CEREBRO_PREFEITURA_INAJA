// Wireframe A · QUIET — refined, generous spacing, left-border priority, monochrome
// Wireframe B · COMPACT — single-line rows, max info density

function WFColHead({ icon, title, count, accent }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "10px 14px 10px",
      borderBottom: "1.5px solid #1f1d1a",
      gap: 10,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, flex: 1, overflow: "hidden" }}>
        <span style={{
          width: 10, height: 10, borderRadius: "50%",
          background: accent, border: "1.5px solid #1f1d1a", flexShrink: 0,
        }}></span>
        <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 16, color: "#1f1d1a", fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {title}
        </span>
      </div>
      <span style={{
        fontFamily: "'Patrick Hand', cursive", fontSize: 13,
        padding: "1px 9px", borderRadius: 12,
        border: "1.5px solid #1f1d1a", background: "#fffdf7",
        flexShrink: 0,
      }}>{count}</span>
    </div>
  );
}

function WFColumn({ title, accent, children, count }) {
  return (
    <div style={{
      flex: 1, minWidth: 0,
      border: "1.5px solid #1f1d1a",
      borderRadius: 12,
      background: "#fbf8ef",
      display: "flex", flexDirection: "column",
      boxShadow: "3px 3px 0 #1f1d1a",
    }}>
      <WFColHead title={title} accent={accent} count={count} />
      <div style={{ padding: 10, display: "flex", flexDirection: "column", gap: 10 }}>
        {children}
      </div>
    </div>
  );
}

// ============================================================================
// WIREFRAME A · QUIET — refined institutional. Priority as left border only.
// ============================================================================
function WFQuietCard({ item, density, showValor }) {
  const pri = WF_PRI[item.p];
  const pad = density === "compact" ? "8px 10px 8px 12px" : density === "comfy" ? "14px 14px 14px 16px" : "10px 12px 10px 14px";
  const gap = density === "compact" ? 4 : density === "comfy" ? 8 : 6;
  return (
    <div style={{
      border: "1.5px solid #1f1d1a",
      borderLeft: `5px solid ${pri.ink}`,
      borderRadius: 8,
      background: "#fffdf7",
      padding: pad,
      display: "flex", flexDirection: "column", gap,
    }}>
      <div style={{
        fontFamily: "'Patrick Hand', cursive", fontSize: density === "compact" ? 13 : 14,
        color: "#1f1d1a", lineHeight: 1.2, fontWeight: 700,
      }}>{item.t}</div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, overflow: "hidden" }}>
          <span style={{
            width: 18, height: 18, borderRadius: "50%",
            background: WF_AVATARS[item.whoI] || "#888",
            color: "#fffdf7", fontSize: 10, fontFamily: "'Patrick Hand', cursive",
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            border: "1.5px solid #1f1d1a", flexShrink: 0,
          }}>{item.whoI}</span>
          <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 12, color: "#4a4641", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.who}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "'Patrick Hand', cursive", fontSize: 11, color: "#8a857d", flexShrink: 0, flexWrap: "nowrap", whiteSpace: "nowrap" }}>
          {item.attach > 0 && <span title="anexos">📎 {item.attach}</span>}
          {showValor && item.valor && <span style={{ color: "#1f1d1a", fontWeight: 700 }}>{item.valor}</span>}
          <span>{item.date}</span>
        </div>
      </div>
    </div>
  );
}

function WFQuiet({ density, showValor }) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", background: "#f5f3ec", overflow: "hidden" }}>
      <WFNavBar />
      <WFHero variant="A" />
      <WFToolbar />
      <div style={{ padding: 18, display: "flex", gap: 14, flex: 1, minHeight: 0 }}>
        <WFColumn title="A Fazer"     accent="#3b6db8" count={WF_DATA.todo.length}>
          {WF_DATA.todo.slice(0, density === "compact" ? 6 : 5).map((it, i) => <WFQuietCard key={i} item={it} density={density} showValor={showValor} />)}
        </WFColumn>
        <WFColumn title="Em Progresso" accent="#d68040" count={WF_DATA.doing.length}>
          {WF_DATA.doing.map((it, i) => <WFQuietCard key={i} item={it} density={density} showValor={showValor} />)}
        </WFColumn>
        <WFColumn title="Concluído"    accent="#4a8a5a" count={WF_DATA.done.length}>
          {WF_DATA.done.slice(0, density === "compact" ? 6 : 4).map((it, i) => <WFQuietCard key={i} item={it} density={density} showValor={showValor} />)}
        </WFColumn>
      </div>
    </div>
  );
}

// ============================================================================
// WIREFRAME B · COMPACT — single-line rows, max info density
// ============================================================================
function WFCompactRow({ item, density, showValor }) {
  const pri = WF_PRI[item.p];
  const h = density === "compact" ? 26 : density === "comfy" ? 38 : 32;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "0 10px 0 0",
      borderBottom: "1px solid #d6d1c4",
      height: h,
      fontFamily: "'Patrick Hand', cursive",
    }}>
      <span style={{ width: 5, height: "70%", background: pri.ink, borderRadius: 2, flexShrink: 0 }}></span>
      <span style={{
        width: 18, height: 18, borderRadius: "50%",
        background: WF_AVATARS[item.whoI] || "#888",
        color: "#fffdf7", fontSize: 10,
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        border: "1.5px solid #1f1d1a", flexShrink: 0,
      }}>{item.whoI}</span>
      <span style={{
        flex: 1, fontSize: 13, color: "#1f1d1a",
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
      }}>{item.t}</span>
      {item.attach > 0 && (
        <span style={{ fontSize: 11, color: "#4a4641", flexShrink: 0 }}>📎{item.attach}</span>
      )}
      {showValor && item.valor && (
        <span style={{ fontSize: 11, color: "#1f1d1a", fontWeight: 700, flexShrink: 0 }}>{item.valor}</span>
      )}
      <span style={{
        fontSize: 9, color: pri.ink,
        padding: "1px 5px", border: `1px solid ${pri.ink}`, borderRadius: 3,
        textTransform: "uppercase", letterSpacing: ".05em", flexShrink: 0,
      }}>{pri.label}</span>
      <span style={{ fontSize: 10, color: "#8a857d", flexShrink: 0 }}>{item.date}</span>
    </div>
  );
}

function WFCompactColumn({ title, accent, items, count, density, showValor }) {
  return (
    <div style={{
      flex: 1, minWidth: 0,
      border: "1.5px solid #1f1d1a",
      borderRadius: 10,
      background: "#fbf8ef",
      display: "flex", flexDirection: "column",
      boxShadow: "3px 3px 0 #1f1d1a",
      overflow: "hidden",
    }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 12px",
        background: "#1f1d1a", color: "#fffdf7",
        gap: 8,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, overflow: "hidden" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: accent, flexShrink: 0 }}></span>
          <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 15, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{title}</span>
        </div>
        <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 13, flexShrink: 0 }}>{count}</span>
      </div>
      <div style={{ paddingLeft: 4 }}>
        {items.map((it, i) => <WFCompactRow key={i} item={it} density={density} showValor={showValor} />)}
      </div>
    </div>
  );
}

function WFCompact({ density, showValor }) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", background: "#f5f3ec", overflow: "hidden" }}>
      <WFNavBar />
      <WFHero variant="B" />
      <WFToolbar />
      <div style={{ padding: 14, display: "flex", gap: 12, flex: 1, minHeight: 0 }}>
        <WFCompactColumn title="A Fazer"      accent="#7faedc" count={WF_DATA.todo.length} items={WF_DATA.todo} density={density} showValor={showValor} />
        <WFCompactColumn title="Em Progresso" accent="#e3a570" count={WF_DATA.doing.length} items={WF_DATA.doing} density={density} showValor={showValor} />
        <WFCompactColumn title="Concluído"    accent="#7fb693" count={WF_DATA.done.length} items={WF_DATA.done} density={density} showValor={showValor} />
      </div>
    </div>
  );
}

window.WFQuiet = WFQuiet;
window.WFCompact = WFCompact;
