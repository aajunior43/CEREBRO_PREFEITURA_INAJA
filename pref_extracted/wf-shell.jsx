// Shared shell pieces — header, toolbar, column wrap
// All wireframes embed inside an artboard. Density tweak adjusts paddings.

const { useState } = React;

// Logo placeholder (no real brand — just a wireframed shield)
function WFLogo({ size = 40 }) {
  return (
    <div style={{
      width: size, height: size,
      border: "1.5px solid #1f1d1a",
      borderRadius: "8px 8px 14px 14px",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "'Patrick Hand', cursive",
      fontSize: size * 0.32,
      color: "#1f1d1a",
      background: "#fffdf7",
      lineHeight: 1,
      flexShrink: 0,
    }}>
      P.M.
    </div>
  );
}

function WFNavBar() {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "10px 18px",
      borderBottom: "1.5px solid #1f1d1a",
      gap: 16,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <WFLogo size={32} />
        <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 15, color: "#1f1d1a" }}>
          Prefeitura de Inajá · Mural
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 18, fontFamily: "'Patrick Hand', cursive", fontSize: 14, color: "#4a4641" }}>
        <span>Credores</span>
        <span>Módulos ▾</span>
        <span style={{
          width: 26, height: 26, borderRadius: "50%",
          border: "1.5px solid #1f1d1a", display: "inline-flex",
          alignItems: "center", justifyContent: "center", fontSize: 11,
        }}>J</span>
      </div>
    </div>
  );
}

// Verse hero — kept as user requested but more refined
function WFHero({ variant = "A" }) {
  // 4 different treatments of the verse — but all keep it as the headline
  if (variant === "B") {
    // Compact: smaller, one row
    return (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 18px",
        gap: 12,
        borderBottom: "1px dashed #1f1d1a",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, minWidth: 0, flex: 1, overflow: "hidden" }}>
          <span style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 11, color: "#8a857d", textTransform: "uppercase", letterSpacing: ".08em", flexShrink: 0 }}>Salmo</span>
          <span style={{ fontFamily: "'Caveat', cursive", fontSize: 22, color: "#1f1d1a", lineHeight: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            O Senhor é meu pastor e nada me faltará
          </span>
        </div>
        <WFBtn primary>+ Criar Recado</WFBtn>
      </div>
    );
  }
  if (variant === "C") {
    // Editorial: serif-feel, large, centered
    return (
      <div style={{
        padding: "22px 24px 18px",
        textAlign: "center",
        borderBottom: "1.5px solid #1f1d1a",
        position: "relative",
        flexShrink: 0,
      }}>
        <div style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 10, color: "#8a857d", letterSpacing: ".18em", textTransform: "uppercase", marginBottom: 6 }}>
          ✦ Salmo 23 ✦
        </div>
        <div style={{
          fontFamily: "'Caveat', cursive",
          fontSize: 30,
          color: "#1f1d1a",
          lineHeight: 1.05,
          letterSpacing: ".01em",
          whiteSpace: "nowrap",
        }}>
          O Senhor é meu pastor <span style={{ color: "#6a655c" }}>e nada me faltará</span>
        </div>
        <div style={{ position: "absolute", right: 24, top: 22 }}>
          <WFBtn primary>+ Criar Recado</WFBtn>
        </div>
      </div>
    );
  }
  if (variant === "D") {
    // Assignee: verse on left like a banner card, with team avatars on right
    return (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "18px 22px",
        gap: 18,
        borderBottom: "1.5px solid #1f1d1a",
        background: "repeating-linear-gradient(135deg, transparent 0 14px, rgba(31,29,26,.025) 14px 15px)",
        flexShrink: 0,
      }}>
        <div style={{ minWidth: 0, overflow: "hidden" }}>
          <div style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 10, color: "#8a857d", letterSpacing: ".18em", textTransform: "uppercase", marginBottom: 4 }}>
            Salmo 23
          </div>
          <div style={{ fontFamily: "'Caveat', cursive", fontSize: 26, color: "#1f1d1a", lineHeight: 1.1, whiteSpace: "nowrap" }}>
            O Senhor é meu pastor e nada me faltará
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexShrink: 0 }}>
          <div style={{ display: "flex" }}>
            {["J","M","R","A"].map((i, idx) => (
              <span key={i} style={{
                width: 28, height: 28, borderRadius: "50%",
                border: "1.5px solid #1f1d1a",
                background: "#fffdf7",
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                fontFamily: "'Patrick Hand', cursive", fontSize: 13,
                marginLeft: idx === 0 ? 0 : -8,
              }}>{i}</span>
            ))}
          </div>
          <WFBtn primary>+ Criar Recado</WFBtn>
        </div>
      </div>
    );
  }
  // A — Quiet: refined, smaller verse, left-aligned with subtle "Salmo 23" eyebrow
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "18px 22px 16px",
      gap: 18,
      borderBottom: "1.5px solid #1f1d1a",
      flexShrink: 0,
    }}>
      <div style={{ minWidth: 0, overflow: "hidden" }}>
        <div style={{ fontFamily: "'Patrick Hand', cursive", fontSize: 10, color: "#8a857d", letterSpacing: ".18em", textTransform: "uppercase", marginBottom: 4 }}>
          ✦ Salmo 23
        </div>
        <div style={{ fontFamily: "'Caveat', cursive", fontSize: 28, color: "#1f1d1a", lineHeight: 1, letterSpacing: ".005em", whiteSpace: "nowrap" }}>
          O Senhor é meu pastor e nada me faltará
        </div>
      </div>
      <WFBtn primary>+ Criar Recado</WFBtn>
    </div>
  );
}

function WFBtn({ children, primary, ghost }) {
  const base = {
    fontFamily: "'Patrick Hand', cursive",
    fontSize: 14,
    padding: "7px 14px",
    border: "1.5px solid #1f1d1a",
    borderRadius: 10,
    cursor: "pointer",
    background: "#fffdf7",
    color: "#1f1d1a",
    boxShadow: primary ? "2px 2px 0 #1f1d1a" : "none",
    whiteSpace: "nowrap",
  };
  if (primary) base.background = "#1f1d1a", base.color = "#fffdf7";
  if (ghost) base.boxShadow = "none";
  return <span style={base}>{children}</span>;
}

function WFToolbar({ variant = "A" }) {
  const inputStyle = {
    fontFamily: "'Patrick Hand', cursive",
    fontSize: 13,
    padding: "6px 12px",
    border: "1.5px solid #1f1d1a",
    borderRadius: 8,
    background: "#fffdf7",
    color: "#4a4641",
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    whiteSpace: "nowrap",
    flexShrink: 0,
  };
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "10px 18px",
      borderBottom: "1.5px solid #1f1d1a",
      flexShrink: 0,
    }}>
      <span style={{ ...inputStyle, flex: 1, minWidth: 160, maxWidth: 320 }}>
        <span style={{ opacity: .5 }}>⌕</span>
        <span style={{ color: "#8a857d" }}>Pesquisar recados...</span>
      </span>
      <span style={inputStyle}>Categoria ▾</span>
      <span style={inputStyle}>Prioridade ▾</span>
      <span style={inputStyle}>Responsável ▾</span>
      <span style={{ ...inputStyle, background: "#1f1d1a", color: "#fffdf7" }}>● Meus</span>
      <span style={{ flex: 1 }}></span>
      <span style={inputStyle}>↻ Atualizar</span>
    </div>
  );
}

window.WFLogo = WFLogo;
window.WFNavBar = WFNavBar;
window.WFHero = WFHero;
window.WFBtn = WFBtn;
window.WFToolbar = WFToolbar;
