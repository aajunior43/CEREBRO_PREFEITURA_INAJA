// Wireframe C · EDITORIAL — generous, hierarchical, almost like notes
// Wireframe D · ASSIGNEE-FIRST — big avatar lead, priority as tag

// ============================================================================
// WIREFRAME C · EDITORIAL — notebook-like cards, clear hierarchy
// ============================================================================
function WFEditorialCard({ item, density, showValor }) {
  const pri = WF_PRI[item.p];
  const pad = density === "compact" ? 10 : density === "comfy" ? 16 : 12;
  return (
    <div style={{
      background: "#fffdf7",
      border: "1.5px solid #1f1d1a",
      borderRadius: 4,
      padding: pad,
      display: "flex", flexDirection: "column",
      gap: density === "compact" ? 6 : 9,
      position: "relative",
      boxShadow: "2px 2px 0 #d6d1c4",
    }}>
      {/* priority eyebrow */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{
          fontFamily: "'Patrick Hand', cursive",
          fontSize: 9, letterSpacing: ".15em",
          color: pri.ink, textTransform: "uppercase",
        }}>
          ◆ {pri.label}
        </span>
        {showValor && item.valor && (
          <span style={{
            fontFamily: "'Patrick Hand', cursive", fontSize: 11,
            color: "#1f1d1a", fontWeight: 700,
            padding: "1px 7px", border: "1px dashed #1f1d1a", borderRadius: 10,
          }}>{item.valor}</span>
        )}
      </div>

      <div style={{
        fontFamily: "'Patrick Hand', cursive",
        fontSize: density === "compact" ? 14 : 16,
        color: "#1f1d1a", lineHeight: 1.2, fontWeight: 700,
      }}>{item.t}</div>

      <div style={{ borderTop: "1px dashed #c9c4ba", paddingTop: density === "compact" ? 5 : 7, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{
            width: 22, height: 22, borderRadius: "50%",
            background: WF_AVATARS[item.whoI] || "#888",
            color: "#fffdf7", fontSize: 11,
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            border: "1.5px solid #1f1d1a", flexShrink: 0,
            fontFamily: "'Patrick Hand', cursive",
          }}>{item.whoI}</span>
          <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 12, color: "#1f1d1a" }}>{item.who}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "'Patrick Hand', cursive", fontSize: 11, color: "#8a857d" }}>
          {item.attach > 0 && (
            <span style={{
              padding: "1px 6px", border: "1px solid #c9c4ba", borderRadius: 10,
              color: "#4a4641",
            }}>📎 {item.attach}</span>
          )}
          <span>{item.date}</span>
        </div>
      </div>
    </div>
  );
}

function WFEditorialColumn({ title, n, items, accent, density, showValor }) {
  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{
        display: "flex", alignItems: "baseline", justifyContent: "space-between",
        paddingBottom: 8,
        borderBottom: `2px solid ${accent}`,
        gap: 8,
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, minWidth: 0, overflow: "hidden" }}>
          <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 18, color: "#1f1d1a", fontWeight: 700, whiteSpace: "nowrap" }}>{title}</span>
          <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 12, color: "#8a857d", flexShrink: 0 }}>· {n}</span>
        </div>
        <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 11, color: "#8a857d", flexShrink: 0, whiteSpace: "nowrap" }}>+ adicionar</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {items.map((it, i) => <WFEditorialCard key={i} item={it} density={density} showValor={showValor} />)}
      </div>
    </div>
  );
}

function WFEditorial({ density, showValor }) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", background: "#f5f3ec", overflow: "hidden" }}>
      <WFNavBar />
      <WFHero variant="C" />
      <WFToolbar />
      <div style={{ padding: 22, display: "flex", gap: 22, flex: 1, minHeight: 0 }}>
        <WFEditorialColumn title="A fazer"      accent="#3b6db8" n={WF_DATA.todo.length}  items={WF_DATA.todo.slice(0, density === "compact" ? 5 : 4)}  density={density} showValor={showValor} />
        <WFEditorialColumn title="Em progresso" accent="#d68040" n={WF_DATA.doing.length} items={WF_DATA.doing} density={density} showValor={showValor} />
        <WFEditorialColumn title="Concluído"    accent="#4a8a5a" n={WF_DATA.done.length}  items={WF_DATA.done.slice(0, density === "compact" ? 5 : 4)}  density={density} showValor={showValor} />
      </div>
    </div>
  );
}

// ============================================================================
// WIREFRAME D · ASSIGNEE-FIRST — big avatar leads, priority as tag
// ============================================================================
function WFAssigneeCard({ item, density, showValor }) {
  const pri = WF_PRI[item.p];
  const pad = density === "compact" ? "9px 11px" : density === "comfy" ? "14px 14px" : "11px 12px";
  const av = density === "compact" ? 30 : density === "comfy" ? 40 : 34;
  return (
    <div style={{
      background: "#fffdf7",
      border: "1.5px solid #1f1d1a",
      borderRadius: 12,
      padding: pad,
      display: "flex", gap: 10, alignItems: "flex-start",
    }}>
      <div style={{
        width: av, height: av, borderRadius: "50%",
        background: WF_AVATARS[item.whoI] || "#888",
        color: "#fffdf7", fontSize: av * 0.42,
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        border: "1.5px solid #1f1d1a", flexShrink: 0,
        fontFamily: "'Patrick Hand', cursive",
      }}>{item.whoI}</div>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div style={{
            fontFamily: "'Patrick Hand', cursive",
            fontSize: density === "compact" ? 13 : 14, color: "#1f1d1a",
            fontWeight: 700, lineHeight: 1.2,
          }}>{item.t}</div>
          <span style={{
            fontFamily: "'Patrick Hand', cursive", fontSize: 9,
            color: pri.ink, background: pri.soft,
            padding: "1px 7px", borderRadius: 10, border: `1px solid ${pri.ink}`,
            letterSpacing: ".06em", textTransform: "uppercase",
            flexShrink: 0, whiteSpace: "nowrap",
          }}>{pri.label}</span>
        </div>
        <div style={{
          fontFamily: "'Patrick Hand', cursive", fontSize: 11, color: "#8a857d",
          display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
        }}>
          <span style={{ color: "#4a4641" }}>{item.who}</span>
          <span>·</span>
          <span>{item.date}</span>
          {item.attach > 0 && (<><span>·</span><span>📎 {item.attach} anexo{item.attach > 1 ? "s" : ""}</span></>)}
          {showValor && item.valor && (<><span>·</span><span style={{ color: "#1f1d1a", fontWeight: 700 }}>{item.valor}</span></>)}
        </div>
      </div>
    </div>
  );
}

function WFAssigneeColumn({ title, accent, items, count, density, showValor }) {
  return (
    <div style={{
      flex: 1, minWidth: 0,
      borderRadius: 14,
      background: "#fbf8ef",
      border: "1.5px solid #1f1d1a",
      display: "flex", flexDirection: "column",
      overflow: "hidden",
    }}>
      <div style={{
        padding: "10px 14px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1.5px solid #1f1d1a",
        background: accent + "22",
        gap: 8,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, overflow: "hidden" }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: accent, border: "1.5px solid #1f1d1a", flexShrink: 0 }}></span>
          <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 16, color: "#1f1d1a", fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{title}</span>
        </div>
        <span style={{
          fontFamily: "'Patrick Hand', cursive", fontSize: 12,
          padding: "1px 8px", borderRadius: 10,
          background: "#1f1d1a", color: "#fffdf7",
          flexShrink: 0,
        }}>{count}</span>
      </div>
      <div style={{ padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((it, i) => <WFAssigneeCard key={i} item={it} density={density} showValor={showValor} />)}
      </div>
    </div>
  );
}

function WFAssignee({ density, showValor }) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", background: "#f5f3ec", overflow: "hidden" }}>
      <WFNavBar />
      <WFHero variant="D" />
      <WFToolbar />
      <div style={{ padding: 18, display: "flex", gap: 14, flex: 1, minHeight: 0 }}>
        <WFAssigneeColumn title="A Fazer"      accent="#3b6db8" count={WF_DATA.todo.length}  items={WF_DATA.todo.slice(0, density === "compact" ? 6 : 5)}  density={density} showValor={showValor} />
        <WFAssigneeColumn title="Em Progresso" accent="#d68040" count={WF_DATA.doing.length} items={WF_DATA.doing} density={density} showValor={showValor} />
        <WFAssigneeColumn title="Concluído"    accent="#4a8a5a" count={WF_DATA.done.length}  items={WF_DATA.done.slice(0, density === "compact" ? 5 : 4)}  density={density} showValor={showValor} />
      </div>
    </div>
  );
}

window.WFEditorial = WFEditorial;
window.WFAssignee = WFAssignee;
