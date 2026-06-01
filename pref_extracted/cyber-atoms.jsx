// Cyberpunk mural — atoms (corner brackets, neon buttons, mono labels, avatars).

const { useState, useEffect } = React;

// =============================================================================
// Atoms
// =============================================================================
function CornerBrackets({ color = "var(--accent)", size = 10, thickness = 1.5, inset = 4, glow = true }) {
  const arms = size;
  const base = { position: "absolute", width: arms, height: arms, borderStyle: "solid", borderColor: color, pointerEvents: "none" };
  const filter = glow ? { filter: `drop-shadow(0 0 4px ${color})` } : {};
  return (
    <>
      <span style={{ ...base, ...filter, top: inset, left: inset,   borderWidth: `${thickness}px 0 0 ${thickness}px` }}></span>
      <span style={{ ...base, ...filter, top: inset, right: inset,  borderWidth: `${thickness}px ${thickness}px 0 0` }}></span>
      <span style={{ ...base, ...filter, bottom: inset, left: inset,  borderWidth: `0 0 ${thickness}px ${thickness}px` }}></span>
      <span style={{ ...base, ...filter, bottom: inset, right: inset, borderWidth: `0 ${thickness}px ${thickness}px 0` }}></span>
    </>
  );
}

function MonoLabel({ children, color = "var(--ink-3)", size = 10, ls = ".2em", style = {} }) {
  return (
    <span className="mono" style={{
      fontSize: size,
      letterSpacing: ls,
      textTransform: "uppercase",
      color,
      fontWeight: 500,
      ...style,
    }}>{children}</span>
  );
}

function NeonBtn({ children, accent, primary, onClick, style = {} }) {
  const c = accent || "var(--accent)";
  if (primary) {
    return (
      <button onClick={onClick} className="mono" style={{
        background: `linear-gradient(180deg, ${c}26, ${c}10)`,
        border: `1px solid ${c}`,
        color: c,
        padding: "9px 16px",
        fontSize: 11,
        letterSpacing: ".25em",
        textTransform: "uppercase",
        fontWeight: 600,
        cursor: "pointer",
        borderRadius: 2,
        boxShadow: `0 0 14px ${c}40, inset 0 0 14px ${c}18`,
        fontFamily: "'JetBrains Mono', monospace",
        position: "relative",
        ...style,
      }}>{children}</button>
    );
  }
  return (
    <button onClick={onClick} className="mono" style={{
      background: "transparent",
      border: "1px solid var(--line-hi)",
      color: "var(--ink-2)",
      padding: "8px 14px",
      fontSize: 11,
      letterSpacing: ".18em",
      textTransform: "uppercase",
      fontWeight: 500,
      cursor: "pointer",
      borderRadius: 2,
      fontFamily: "'JetBrains Mono', monospace",
      ...style,
    }}>{children}</button>
  );
}

const PRIO = {
  urgente: { ink: "var(--p-urg)", code: "URG", label: "URGENTE" },
  alta:    { ink: "var(--p-alt)", code: "ALT", label: "ALTA" },
  media:   { ink: "var(--p-med)", code: "MED", label: "MÉDIA" },
  baixa:   { ink: "var(--p-bai)", code: "LOW", label: "BAIXA" },
};

const AVATAR_BG = {
  J: "#1a4566",
  M: "#481a66",
  R: "#664a1a",
};

function Avatar({ ch, size = 22, accent }) {
  const bg = AVATAR_BG[ch] || "#1a2640";
  return (
    <span className="mono" style={{
      width: size, height: size, display: "inline-flex",
      alignItems: "center", justifyContent: "center",
      background: bg,
      color: "var(--ink)",
      fontSize: size * 0.45,
      fontWeight: 600,
      border: `1px solid ${accent || "var(--line-hi)"}`,
      borderRadius: 2,
      flexShrink: 0,
      boxShadow: `0 0 0 1px var(--bg-panel) inset`,
    }}>{ch}</span>
  );
}

window.CYBER = { CornerBrackets, MonoLabel, NeonBtn, Avatar, PRIO };
