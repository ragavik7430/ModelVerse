

'use client';

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, fetchHealth, type HealthCheckResult } from "@/lib/api";

type Mode = "engineering" | "learning";
const stages = [
  ["01", "Problem", "Define the outcome you need."],
  ["02", "Dataset", "Connect the data behind the problem."],
  ["03", "Data quality", "Understand coverage and readiness."],
  ["04", "Recommendation", "Review a recommended approach."],
  ["05", "Training", "Train and compare experiments."],
  ["06", "Explainability", "Understand what shaped predictions."],
  ["07", "Deployment", "Bring a validated model to production."],
  ["08", "Monitoring", "Track performance and improve."],
];
const navItems = ["Overview", "Projects", "Experiments", "Models", "Deployments", "Monitoring"];

export default function Home() {
  const [mode, setMode] = useState<Mode>("engineering");
  const [health, setHealth] = useState<HealthCheckResult | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const refresh = useCallback(() => { void fetchHealth().then(setHealth); }, []);
  useEffect(() => {
    const checkHealth = () => { void fetchHealth().then(setHealth); };
    checkHealth();
    const timer = window.setInterval(checkHealth, 30000);
    return () => window.clearInterval(timer);
  }, []);
  const connected = health?.available === true && health.data.status === "healthy";

  return <div className="app-shell">
    {menuOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Main navigation">
      <a className="brand" href="#overview" aria-label="ModelVerse overview"><span className="brand-mark">MV</span><span className="brand-copy"><strong>ModelVerse</strong><small>AI ENGINEERING WORKSPACE</small></span></a>
      <div className="workspace-label">WORKSPACE</div>
      <nav className="nav-list">{navItems.map((label, index) => <a key={label} href={index === 0 ? "#overview" : "#"} className={`nav-item ${index === 0 ? "active" : ""}`} aria-current={index === 0 ? "page" : undefined} onClick={index === 0 ? () => setMenuOpen(false) : e => e.preventDefault()}><span className="nav-marker" aria-hidden="true" /> <span>{label}</span>{index !== 0 && <span className="nav-soon">Soon</span>}</a>)}</nav>
      <div className="sidebar-spacer" />
      <nav className="nav-list utility-nav" aria-label="Workspace settings"><a className="nav-item" href="#documentation"><span className="nav-marker" aria-hidden="true" /><span>Documentation</span></a><a className="nav-item" href="#settings" onClick={e => e.preventDefault()}><span className="nav-marker" aria-hidden="true" /><span>Settings</span><span className="nav-soon">Soon</span></a></nav>
      <div className="sidebar-profile"><div className="avatar">MV</div><div className="profile-copy"><strong>Workspace</strong><small>Personal workspace</small></div></div>
    </aside>
    <div className="main-column" id="overview">
      <header className="topbar"><div className="topbar-left"><button className="mobile-menu" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation" aria-expanded={menuOpen}><span /><span /><span /></button><span className="crumb">Workspace</span><span className="crumb-slash">/</span><strong>Overview</strong></div><div className="topbar-right"><div className="mode-switch" role="group" aria-label="Presentation mode"><button className={mode === "engineering" ? "selected" : ""} onClick={() => setMode("engineering")} aria-pressed={mode === "engineering"}>Engineering</button><button className={mode === "learning" ? "selected" : ""} onClick={() => setMode("learning")} aria-pressed={mode === "learning"}>Learning</button></div><div className="top-status"><span className={`status-dot ${connected ? "up" : "down"}`} />{connected ? "System status" : "API unavailable"}</div><button className="top-avatar" aria-label="User profile">MV</button></div></header>
      <main className="content">
        <section className="hero"><div className="hero-copy"><div className="eyebrow">AI SOLUTION ENGINEERING <span className="eyebrow-version">PHASE 01</span></div><h1>Build AI solutions<br /><span>from problem to production.</span></h1><p>ModelVerse brings problem understanding, data analysis, AI recommendations, experimentation, explainability, deployment and monitoring into one engineering workspace.</p><div className="hero-actions"><button className="button-primary" disabled title="Project creation is not implemented yet">Create Project</button><a className="button-secondary" href="#lifecycle">Explore Workflow</a></div></div><div className="hero-aside"><span className="hero-aside-label">ENGINEERING WORKFLOW</span><strong>Problem <span /> Production</strong><div className="hero-progress"><i /></div><span className="hero-aside-note">8 connected stages</span></div></section>
        <section className="metrics" aria-label="Workspace metrics"><Metric title="Pipeline" value="Not configured"/><Metric title="Dataset" value="No dataset"/><Metric title="Experiments" value="0"/><Metric title="Models" value="0"/><Metric title="Deployments" value="0"/></section>
        {mode === "learning" && <section className="learning-section" aria-label="Learning mode explanations"><SectionHeader kicker="LEARNING MODE" title="How ModelVerse works" detail="A guided overview of the decisions behind each stage."/><div className="learning-grid"><article><span>01</span><h3>Why start with the problem?</h3><p>A clear outcome helps determine which data, methods, and success measures are relevant.</p></article><article><span>02</span><h3>How AI recommendations will work</h3><p>Recommendations will connect the problem and available data to a reasoned solution approach.</p></article><article><span>03</span><h3>Why experiments are tracked</h3><p>Recorded runs make it possible to compare choices and understand how a model was produced.</p></article></div></section>}
        <section className="workflow-section" id="lifecycle"><SectionHeader kicker="THE MODELVERSE WORKFLOW" title="From problem to production" detail={mode === "learning" ? "One connected process, with explanations alongside the engineering." : "A clear path through every stage of AI solution engineering."}/><div className="workflow-grid">{stages.map(([number, title, description]) => <article className="stage" key={number}><span className="stage-number">{number}</span><h3>{title}</h3><p>{description}</p><span className="stage-status">Planned</span></article>)}</div></section>
        <section className="lower-grid"><article className="problem-card"><div className="section-kicker">PROBLEM DEFINITION</div><h2>Start with the problem.</h2><p className="problem-subtitle">What are you trying to solve?</p><label className="sr-only" htmlFor="problem">Describe a business or engineering problem</label><textarea id="problem" placeholder="Describe a business or engineering problem..." disabled/><div className="problem-footer"><span className="phase-badge">Coming in Phase 3/4</span><button className="button-primary" disabled>Analyze Problem</button></div></article><SystemStatus health={health} onRefresh={refresh}/></section>
        <footer className="footer"><span>ModelVerse <span className="footer-divider">/</span> AI Engineering Workspace</span><span><i className={`status-dot ${connected ? "up" : "down"}`}/>{connected ? "API connected" : "API unavailable"}</span></footer>
      </main>
    </div>
  </div>;
}
function Metric({ title, value }: { title: string; value: string }) { return <article className="metric"><span className="metric-title">{title}</span><strong>{value}</strong></article>; }
function SectionHeader({ kicker, title, detail }: { kicker: string; title: string; detail: string }) { return <div className="section-header"><div><span className="section-kicker">{kicker}</span><h2>{title}</h2><p>{detail}</p></div><span className="section-rule"/></div>; }
function SystemStatus({ health, onRefresh }: { health: HealthCheckResult | null; onRefresh: () => void }) {
 const online = health?.available === true && health.data.status === "healthy";
 const response = health?.available ? health.data : null;
 return <article className="status-panel"><div className="status-heading"><div><span className="section-kicker">LIVE CONNECTION</span><h2>System health</h2></div><button className="refresh" onClick={onRefresh} aria-label="Refresh system health">Refresh</button></div><p className="status-summary"><span className={`status-dot ${online ? "up" : "down"}`}/><strong>{online ? "API connected" : "API unavailable"}</strong><span>{online ? "Live" : "Check connection"}</span></p><div className="health-rows"><div><span>Backend API</span><b className={online ? "text-green" : "text-red"}>{online ? "Connected" : "Unavailable"}</b></div><div><span>Service</span><b>{response?.service ?? "Not reported"}</b></div><div><span>Version</span><b>{response?.version ?? "Not reported"}</b></div><div><span>API base</span><b className="mono">{API_BASE_URL}</b></div></div><div className="health-footnote">Automatically checks every 30 seconds</div></article>;
}
