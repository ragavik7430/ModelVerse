"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getProject, getStoredAuthToken, logout, updateProject, type Project } from "@/lib/api";

export default function ProjectDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const load = async () => {
      try {
        const result = await getProject(projectId);
        setProject(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load project.");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [projectId, router]);

  const handleModeChange = async (mode: "engineering" | "learning") => {
    if (!project) return;
    try {
      const updated = await updateProject(project.id, { mode });
      setProject(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update the workspace mode.");
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      router.replace("/login");
    }
  };

  if (loading) {
    return <main className="auth-page"><div className="auth-card"><p className="auth-subtitle">Loading project workspace…</p></div></main>;
  }

  if (!project) {
    return (
      <main className="auth-page">
        <div className="auth-card">
          <h1>Project unavailable</h1>
          <p className="auth-subtitle">{error || "This project could not be loaded."}</p>
          <Link href="/projects" className="button-primary auth-button">Back to projects</Link>
        </div>
      </main>
    );
  }

  const navigation = ["Problem", "Dataset", "Pipeline", "Experiments", "Explainability", "Deployment", "Monitoring"];

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Project workspace navigation">
        <div className="brand">
          <span className="brand-mark">MV</span>
          <span className="brand-copy">
            <strong>ModelVerse</strong>
            <small>AI ENGINEERING WORKSPACE</small>
          </span>
        </div>

        <div className="workspace-label">CURRENT WORKSPACE</div>
        <nav className="nav-list" aria-label="Project sections">
          <Link href="/projects" className="nav-item">
            <span className="nav-marker" aria-hidden="true" />
            <span>Projects</span>
          </Link>
          <span className="nav-item active">
            <span className="nav-marker" aria-hidden="true" />
            <span>{project.name}</span>
          </span>
          {navigation.map((item) => (
            <span key={item} className="nav-item disabled-nav-item">
              <span className="nav-marker" aria-hidden="true" />
              <span>{item}</span>
              <span className="nav-soon">Soon</span>
            </span>
          ))}
        </nav>

        <div className="sidebar-spacer" />
        <button type="button" className="button-secondary signout-button" onClick={handleLogout}>
          Sign out
        </button>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <span className="crumb">Workspace</span>
            <span className="crumb-slash">/</span>
            <strong>{project.name}</strong>
          </div>
          <div className="topbar-right">
            <div className="mode-switch" role="group" aria-label="Project mode switch">
              <button className={project.mode === "engineering" ? "selected" : ""} onClick={() => handleModeChange("engineering")} aria-pressed={project.mode === "engineering"}>
                Engineering
              </button>
              <button className={project.mode === "learning" ? "selected" : ""} onClick={() => handleModeChange("learning")} aria-pressed={project.mode === "learning"}>
                Learning
              </button>
            </div>
          </div>
        </header>

        <main className="content project-detail-page">
          <div className="page-header-row">
            <div>
              <p className="section-kicker">WORKSPACE</p>
              <h1>{project.name}</h1>
              <p className="page-subtitle">Status: {project.status}</p>
            </div>
            <Link href="/projects" className="button-secondary">
              Back to projects
            </Link>
          </div>

          {error ? <div className="error-box">{error}</div> : null}

          <div className="detail-grid">
            <section className="project-detail-card">
              <h2>Problem Statement</h2>
              <p>{project.problem_statement}</p>
            </section>

            <section className="project-detail-card">
              <h2>Objective</h2>
              <p>{project.objective}</p>
            </section>

            <section className="project-detail-card wide-card">
              <h2>Mode</h2>
              <p>{project.mode === "engineering" ? "Engineering Mode" : "Learning Mode"}</p>
              {project.mode === "engineering" ? (
                <div className="mode-copy">
                  <p>Technical language and system configuration are the focus here. This workspace will support technical requirements, lifecycle planning, and engineering-oriented project tracking.</p>
                  <ul>
                    <li>Problem and dataset inputs</li>
                    <li>Engineering execution plan</li>
                    <li>Lifecycle readiness and agent handoffs</li>
                  </ul>
                </div>
              ) : (
                <div className="mode-copy">
                  <p>Learning Mode translates the process into plain-language guidance so you can understand why each stage matters and how ModelVerse will help you move from problem to production.</p>
                  <ul>
                    <li>Explain the objective and the decision context</li>
                    <li>Break down future workspace stages in accessible language</li>
                    <li>Prepare for educational guidance in later phases</li>
                  </ul>
                </div>
              )}
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
