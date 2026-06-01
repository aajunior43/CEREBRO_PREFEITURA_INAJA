// Cyberpunk Mural · main composition

const { useState: _useState, useEffect: _useEffect } = React;

// =============================================================================
// Nav bar
// =============================================================================
function NavBar({ accent }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "14px 28px",
      borderBottom: "1px solid var(--line)",
      background: "linear-gradient(180deg, rgba(255,255,255,.012), transparent)",
      position: "relative",
    }}>
      {/* bottom accent line */}
      <div style={{
        position: "absolute", bottom: -1, left: 28, width: 80, height: 1,
        background: accent,
        boxShadow: `0 0 12px ${accent}`,
      }}></div>

      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        {/* logo placeholder — angular shield */}
        <div style={{
          width: 36, height: 36,
          background: "var(--bg-panel)",
          border: "1px solid var(--line-hi)",
          clipPath: "polygon(0 0, 100% 0, 100% 70%, 50% 100%, 0 70%)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
          color: accent, fontWeight: 700, letterSpacing: ".05em",
          textShadow: `0 0 6px ${accent}`,
        }}>P.M</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <CYBER.MonoLabel size={9} color="var(--ink-3)">PREFEITURA MUNICIPAL // INAJÁ</CYBER.MonoLabel>
          <CYBER.MonoLabel size={13} color="var(--ink)" ls=".15em" style={{ fontWeight: 600 }}>
            MURAL_SYS
          </CYBER.MonoLabel>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
        <CYBER.MonoLabel size={11} color="var(--ink-2)" style={{ cursor: "pointer" }}>‹ CREDORES</CYBER.MonoLabel>
        <CYBER.MonoLabel size={11} color="var(--ink-2)" style={{ cursor: "pointer" }}>‹ MÓDULOS ▾</CYBER.MonoLabel>
        <div style={{ display: "flex", alignItems: "center", gap: 8, paddingLeft: 16, borderLeft: "1px solid var(--line)" }}>
          <CYBER.Avatar ch="J" size={26} accent={accent} />
          <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <CYBER.MonoLabel size={10} color="var(--ink)" ls=".1em" style={{ fontWeight: 600 }}>JOAQUIM</CYBER.MonoLabel>
            <CYBER.MonoLabel size={8} color={accent} ls=".2em">// ADMIN</CYBER.MonoLabel>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Hero — verse in gold with shimmer + neon brackets
// =============================================================================
function Hero({ accent }) {
  return (
    <div style={{
      position: "relative",
      padding: "30px 28px 28px",
      borderBottom: "1px solid var(--line)",
    }}>
      {/* corner brackets framing the verse */}
      <CYBER.CornerBrackets color={accent} size={18} thickness={1.5} inset={14} />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{
              width: 6, height: 6, background: accent, borderRadius: "50%",
              boxShadow: `0 0 8px ${accent}, 0 0 16px ${accent}`,
            }}></span>
            <CYBER.MonoLabel size={10} color={accent} ls=".35em">SALMO_23 // SCRIPTURE.SYS</CYBER.MonoLabel>
          </div>
          <h1 style={{
            margin: 0,
            fontFamily: "'Chakra Petch', sans-serif",
            fontWeight: 700,
            fontSize: "clamp(28px, 4.5vw, 52px)",
            lineHeight: 1,
            letterSpacing: "-.01em",
            textTransform: "uppercase",
            background: "linear-gradient(120deg, #d4af37 0%, #fef1c9 25%, #ffd66e 50%, #fef1c9 75%, #d4af37 100%)",
            backgroundSize: "200% auto",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            filter: "drop-shadow(0 0 18px rgba(255, 194, 74, 0.35))",
            animation: "shineCY 6s linear infinite",
          }}>
            O Senhor é meu pastor<br />
            e nada me faltará
          </h1>
          <style>{`
            @keyframes shineCY { to { background-position: 200% center; } }
            @keyframes pulsePri {
              0%,100% { box-shadow: 0 0 6px var(--p-urg), 0 0 12px var(--p-urg); }
              50%     { box-shadow: 0 0 10px var(--p-urg), 0 0 22px var(--p-urg); }
            }
          `}</style>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-end" }}>
          <CYBER.MonoLabel size={9} color="var(--ink-4)" ls=".3em">[CMD_##] CREATE_NEW</CYBER.MonoLabel>
          <CYBER.NeonBtn primary accent={accent}>+ CRIAR_RECADO</CYBER.NeonBtn>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Toolbar
// =============================================================================
function Toolbar({ accent }) {
  const inputStyle = {
    background: "var(--bg-panel)",
    border: "1px solid var(--line)",
    color: "var(--ink-2)",
    padding: "9px 14px",
    fontSize: 11,
    letterSpacing: ".15em",
    textTransform: "uppercase",
    fontFamily: "'JetBrains Mono', monospace",
    fontWeight: 500,
    borderRadius: 2,
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    whiteSpace: "nowrap",
    flexShrink: 0,
    cursor: "pointer",
  };
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "14px 28px",
      borderBottom: "1px solid var(--line)",
      background: "rgba(255,255,255,.012)",
    }}>
      <div style={{ ...inputStyle, flex: 1, minWidth: 200, maxWidth: 420, gap: 10, cursor: "text" }}>
        <span style={{ color: accent, textShadow: `0 0 6px ${accent}` }}>›_</span>
        <span style={{ color: "var(--ink-4)", letterSpacing: ".1em" }}>SEARCH RECADOS<span style={{
          display: "inline-block", width: 6, height: 11, background: accent, marginLeft: 8,
          verticalAlign: "middle", animation: "blink 1.1s steps(1) infinite",
        }}></span></span>
        <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
      </div>
      <span style={inputStyle}>CATEGORIA <span style={{ color: accent }}>▾</span></span>
      <span style={inputStyle}>PRIORIDADE <span style={{ color: accent }}>▾</span></span>
      <span style={inputStyle}>RESPONSÁVEL <span style={{ color: accent }}>▾</span></span>
      <span style={{
        ...inputStyle,
        borderColor: accent,
        color: accent,
        background: `linear-gradient(180deg, ${accent}1a, transparent)`,
        boxShadow: `0 0 10px ${accent}33, inset 0 0 8px ${accent}1a`,
      }}>● MEUS</span>
      <span style={{ flex: 1 }}></span>
      <span style={inputStyle}>↻ REFRESH</span>
    </div>
  );
}

window.CYBER_LAYOUT = { NavBar, Hero, Toolbar };
