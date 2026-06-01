// Cyberpunk Mural · cards + columns + App composition

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "density": "regular",
  "showValor": true,
  "accent": "#00f0ff",
  "scanlines": true,
  "grid": true
}/*EDITMODE-END*/;

// =============================================================================
// Card
// =============================================================================
function CyberCard({ item, density, showValor, accent }) {
  const p = CYBER.PRIO[item.p];
  const isUrgent = item.p === "urgente";
  const pad = density === "compact" ? "10px 12px" : density === "comfy" ? "16px 16px" : "12px 14px";
  const titleSize = density === "compact" ? 14 : density === "comfy" ? 17 : 15;

  return (
    <div style={{
      position: "relative",
      background: "linear-gradient(180deg, rgba(255,255,255,.018), transparent 60%), var(--bg-card)",
      border: "1px solid var(--line)",
      borderRadius: 2,
      padding: pad,
      display: "flex", flexDirection: "column", gap: density === "compact" ? 7 : 10,
      // angular corner cut
      clipPath: "polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px))",
    }}>
      {/* priority neon edge — left */}
      <div style={{
        position: "absolute", top: 8, bottom: 8, left: 0, width: 2,
        background: p.ink,
        boxShadow: `0 0 8px ${p.ink}, 0 0 14px ${p.ink}80`,
        animation: isUrgent ? "pulsePri 1.8s ease-in-out infinite" : "none",
      }}></div>

      {/* top row: priority code + tag + valor */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <span className="mono" style={{
            fontSize: 9, letterSpacing: ".25em", color: p.ink,
            padding: "2px 6px",
            border: `1px solid ${p.ink}`,
            background: `${p.ink}10`,
            textShadow: `0 0 6px ${p.ink}80`,
            fontWeight: 600,
            borderRadius: 1,
            flexShrink: 0,
          }}>[{p.code}]</span>
          <CYBER.MonoLabel size={9} color="var(--ink-4)" ls=".25em">#{String(item.t.length).padStart(3, "0")}</CYBER.MonoLabel>
        </div>
        {showValor && item.valor && (
          <span className="mono" style={{
            fontSize: 10, letterSpacing: ".05em",
            color: "var(--gold)",
            padding: "2px 8px",
            border: "1px solid var(--gold)",
            background: "rgba(255, 194, 74, .08)",
            borderRadius: 1,
            textShadow: "0 0 6px rgba(255, 194, 74, .5)",
            fontWeight: 600,
            flexShrink: 0,
            whiteSpace: "nowrap",
          }}>{item.valor}</span>
        )}
      </div>

      {/* title */}
      <div style={{
        fontFamily: "'Chakra Petch', sans-serif",
        fontWeight: 600,
        fontSize: titleSize,
        lineHeight: 1.15,
        color: "var(--ink)",
        letterSpacing: ".005em",
      }}>{item.t}</div>

      {/* meta row */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 8, paddingTop: density === "compact" ? 4 : 6,
        borderTop: "1px dashed var(--line)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, minWidth: 0, overflow: "hidden" }}>
          <CYBER.Avatar ch={item.whoI} size={20} accent={accent} />
          <CYBER.MonoLabel size={10} color="var(--ink-2)" ls=".08em" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", textTransform: "none" }}>
            {item.who}
          </CYBER.MonoLabel>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          {item.attach > 0 && (
            <span className="mono" style={{
              fontSize: 10, color: accent, letterSpacing: ".1em",
              display: "inline-flex", alignItems: "center", gap: 3,
              textShadow: `0 0 6px ${accent}80`,
            }}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 17.93 8.83l-8.57 8.57a2 2 0 0 1-2.83-2.83l8.49-8.49"/></svg>
              [{String(item.attach).padStart(2,"0")}]
            </span>
          )}
          <CYBER.MonoLabel size={9} color="var(--ink-4)" ls=".15em">{item.date.replace("/", ".")}</CYBER.MonoLabel>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Column
// =============================================================================
function Column({ idx, code, title, accent, count, items, density, showValor, mainAccent }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", gap: 12,
      flex: 1, minWidth: 0,
    }}>
      {/* column header */}
      <div style={{
        position: "relative",
        padding: "12px 16px",
        background: `linear-gradient(180deg, ${accent}14, transparent 80%), var(--bg-panel)`,
        border: "1px solid var(--line)",
        borderTop: `2px solid ${accent}`,
        borderRadius: 2,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 8,
        boxShadow: `inset 0 1px 0 ${accent}40, 0 0 24px ${accent}10`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
          <CYBER.MonoLabel size={10} color={accent} ls=".3em" style={{ textShadow: `0 0 6px ${accent}80` }}>
            [{idx}]
          </CYBER.MonoLabel>
          <CYBER.MonoLabel size={13} color="var(--ink)" ls=".18em" style={{ fontWeight: 600, whiteSpace: "nowrap" }}>
            {title}
          </CYBER.MonoLabel>
          <CYBER.MonoLabel size={9} color="var(--ink-4)" ls=".2em" style={{ whiteSpace: "nowrap" }}>
            // {code}
          </CYBER.MonoLabel>
        </div>
        <div style={{
          padding: "2px 8px",
          border: `1px solid ${accent}`,
          background: `${accent}1a`,
          color: accent,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: ".05em",
          borderRadius: 1,
          textShadow: `0 0 6px ${accent}80`,
          flexShrink: 0,
        }}>{String(count).padStart(2, "0")}</div>
      </div>

      {/* cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {items.length === 0 ? (
          <div style={{
            padding: "32px 16px", textAlign: "center",
            border: "1px dashed var(--line)",
            background: "rgba(255,255,255,.012)",
            borderRadius: 2,
            display: "flex", flexDirection: "column", gap: 8, alignItems: "center",
          }}>
            <CYBER.MonoLabel size={10} color="var(--ink-4)" ls=".3em">[ EMPTY_QUEUE ]</CYBER.MonoLabel>
            <CYBER.MonoLabel size={9} color="var(--ink-4)" ls=".15em" style={{ textTransform: "none" }}>
              mova um card ou inicie uma tarefa
            </CYBER.MonoLabel>
          </div>
        ) : items.map((it, i) => (
          <CyberCard key={i} item={it} density={density} showValor={showValor} accent={mainAccent} />
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// App
// =============================================================================
function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // Apply CSS variables based on tweaks
  React.useEffect(() => {
    document.documentElement.style.setProperty("--accent", t.accent);
    document.documentElement.style.setProperty("--scanline-opacity", t.scanlines ? 0.35 : 0);
    document.documentElement.style.setProperty("--grid-opacity", t.grid ? 0.5 : 0);
  }, [t.accent, t.scanlines, t.grid]);

  return (
    <>
      <CYBER_LAYOUT.NavBar accent={t.accent} />
      <CYBER_LAYOUT.Hero accent={t.accent} />
      <CYBER_LAYOUT.Toolbar accent={t.accent} />

      <div style={{
        padding: "20px 28px 60px",
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 18,
        alignItems: "start",
      }}>
        <Column idx="01" code="TODO" title="A_FAZER" accent="#4d9eff" count={WF_DATA.todo.length}
          items={WF_DATA.todo} density={t.density} showValor={t.showValor} mainAccent={t.accent} />
        <Column idx="02" code="WIP" title="EM_PROGRESSO" accent="#ff8a3d" count={WF_DATA.doing.length}
          items={WF_DATA.doing} density={t.density} showValor={t.showValor} mainAccent={t.accent} />
        <Column idx="03" code="DONE" title="CONCLUÍDO" accent="#4dffa0" count={WF_DATA.done.length}
          items={WF_DATA.done} density={t.density} showValor={t.showValor} mainAccent={t.accent} />
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Sistema" />
        <TweakColor
          label="Cor de acento"
          value={t.accent}
          options={["#00f0ff", "#ff2d8e", "#c8ff2d", "#ffc24a", "#a86bff"]}
          onChange={(v) => setTweak("accent", v)}
        />
        <TweakToggle label="Scanlines" value={t.scanlines} onChange={(v) => setTweak("scanlines", v)} />
        <TweakToggle label="Grid de fundo" value={t.grid} onChange={(v) => setTweak("grid", v)} />

        <TweakSection label="Cartões" />
        <TweakRadio
          label="Densidade"
          value={t.density}
          options={["compact", "regular", "comfy"]}
          onChange={(v) => setTweak("density", v)}
        />
        <TweakToggle label="Mostrar valor R$" value={t.showValor} onChange={(v) => setTweak("showValor", v)} />
      </TweaksPanel>
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
