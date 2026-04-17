/**
 * Titan Cockpit V4 — Monolith (reference layout + design tokens)
 * Primary Streamlit UI lives in command_center_v2.py; this mirrors tokens for React embeds or future split.
 */
import React from "react";

const tokens = {
  bg: "#070708",
  amber: "#f59e0b",
  zinc: "#18181b",
  divider: "rgba(255, 255, 255, 0.05)",
  cardShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
};

const hero = {
  position: "relative",
  minHeight: "42vh",
  background:
    "linear-gradient(180deg, rgba(7,7,8,0.2) 0%, rgba(24,24,27,0.75) 55%, rgba(7,7,8,0.96) 100%), radial-gradient(ellipse 80% 60% at 50% 0%, rgba(245,158,11,0.09), transparent 60%)",
  boxShadow: tokens.cardShadow,
  borderBottom: `1px solid ${tokens.divider}`,
  zIndex: 4,
};

const nav = {
  display: "flex",
  justifyContent: "space-between",
  padding: "1.25rem clamp(1.25rem, 5vw, 3.5rem)",
  fontFamily: "'Inter', system-ui, sans-serif",
  fontSize: "0.65rem",
  fontWeight: 900,
  fontStyle: "italic",
  letterSpacing: "-0.03em",
  textTransform: "uppercase",
  color: "rgba(255,255,255,0.92)",
};

const h2 = {
  fontFamily: "'Inter', system-ui, sans-serif",
  fontSize: "0.72rem",
  fontWeight: 900,
  fontStyle: "italic",
  textTransform: "uppercase",
  letterSpacing: "-0.045em",
  color: tokens.amber,
};

const purposePillar = {
  fontFamily: "'Playfair Display', Georgia, serif",
  fontStyle: "italic",
  letterSpacing: "0.12em",
  color: "rgba(228, 234, 244, 0.9)",
};

const card = {
  background: tokens.zinc,
  border: `1px solid ${tokens.divider}`,
  boxShadow: tokens.cardShadow,
  borderRadius: 12,
};

export function TitanCockpit() {
  return (
    <div style={{ background: tokens.bg, minHeight: "100vh", color: "#e8eef5" }}>
      <link
        href="https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,900;1,900&family=Playfair+Display:ital,wght@0,400..900;1,400..900&display=swap"
        rel="stylesheet"
      />
      <header style={hero}>
        <div style={nav}>
          <span>TITAN COCKPIT</span>
          <span>Monolith V4 · Hardened</span>
          <span>Industrial Amber</span>
        </div>
        <div style={{ padding: "0 2rem 2rem", maxWidth: "42rem" }}>
          <p style={{ color: tokens.amber, fontSize: "0.65rem", letterSpacing: "0.2em", textTransform: "uppercase" }}>
            Execution over information
          </p>
          <h1 style={{ fontFamily: "'Playfair Display', serif", fontSize: "clamp(1.85rem, 5vw, 2.5rem)", margin: "0.5rem 0" }}>
            No clutter. No flinching.
          </h1>
          <p style={purposePillar}>Obsidian baseline · Integrity → Trio → Janitor</p>
        </div>
      </header>
      <main style={{ padding: "2rem", position: "relative", zIndex: 2 }}>
        <h2 style={h2}>Integrity runway</h2>
        <div style={{ ...card, padding: "1.25rem", marginTop: "1rem" }}>Runway card (absolute depth / z-index in Streamlit)</div>
        <h2 style={{ ...h2, marginTop: "2rem" }}>Power trio</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem", marginTop: "1rem" }}>
          {["Combat", "Momentum", "Admin"].map((label) => (
            <div key={label} style={{ ...card, padding: "1rem" }}>
              <div style={{ ...h2, fontSize: "0.62rem" }}>{label}</div>
              <p style={{ fontFamily: "'Playfair Display', serif", margin: "0.5rem 0 0" }}>Task title</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

export default TitanCockpit;
