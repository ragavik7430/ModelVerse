"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getCurrentUser, getProjects, getStoredAuthToken, logout, type AuthUser, type Project } from "@/lib/api";

export default function ProjectsPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
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
        const [currentUser, projectList] = await Promise.all([getCurrentUser(), getProjects()]);
        setUser(currentUser);
        setProjects(projectList);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load workspace.");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [router]);

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      router.replace("/login");
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand">
          <span className="brand-mark">MV</span>
          <span className="brand-copy">
            <strong>ModelVerse</strong>
            <small>AI ENGINEERING WORKSPACE</small>
          </span>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <nav className="nav-list" aria-label="Workspace navigation">
          <Link href="/projects" className="nav-item active">
            <span className="nav-marker" aria-hidden="true" />
            <span>Projects</span>
          </Link>
          {projects[0] ? (
            <Link href={`/projects/${projects[0].id}`} className="nav-item">
              <span className="nav-marker" aria-hidden="true" />
              <span>Current workspace</span>
            </Link>
          ) : (
            <span className="nav-item disabled-nav-item">
              <span className="nav-marker" aria-hidden="true" />
              <span>Current workspace</span>
            </span>
          )}
          <span className="nav-item disabled-nav-item">
            <span className="nav-marker" aria-hidden="true" />
            <span>Problem</span>
            <span className="nav-soon">Soon</span>
          </span>
        </nav>

        <div className="sidebar-spacer" />

        <div className="sidebar-profile">
          <div className="avatar">{user?.email ? user.email.slice(0, 2).toUpperCase() : "MV"}</div>
          <div className="profile-copy">
            <strong>{user?.email ?? "Workspace"}</strong>
            <small>Authenticated</small>
          </div>
        </div>

        <button type="button" className="button-secondary signout-button" onClick={handleLogout}>
          Sign out
        </button>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <span className="crumb">Workspace</span>
            <span className="crumb-slash">/</span>
            <strong>Projects</strong>
          </div>
          <div className="topbar-right">
            <div className="top-status">
              <span className="status-dot up" />
              Signed in
            </div>
          </div>
        </header>

        <main className="content projects-page">
          <div className="page-header-row">
            <div>
              <p className="section-kicker">PROJECTS</p>
              <h1>Projects</h1>
              <p className="page-subtitle">Your AI engineering workspaces.</p>
            </div>
            <Link href="/projects/new" className="button-primary">
              Create Project
            </Link>
          </div>

          {error ? <div className="error-box">{error}</div> : null}

          {loading ? (
            <div className="empty-state">
              <p>Loading projects…</p>
            </div>
          ) : projects.length === 0 ? (
            <div className="empty-state">
              <h3>No projects yet.</h3>
              <p>Start by describing a real problem you want ModelVerse to help solve.</p>
              <Link href="/projects/new" className="button-primary">
                Create Project
              </Link>
            </div>
          ) : (
            <div className="project-grid">
              {projects.map((project) => (
                <article key={project.id} className="project-card">
                  <div className="project-card-header">
                    <div>
                      <span className="project-tag">{project.mode}</span>
                      <h2>{project.name}</h2>
                    </div>
                    <span className="project-status">{project.status}</span>
                  </div>
                  <p className="project-problem">{project.problem_statement}</p>
                  <div className="project-meta">
                    <span>Objective</span>
                    <strong>{project.objective}</strong>
                  </div>
                  <div className="project-actions">
                    <Link href={`/projects/${project.id}`} className="button-secondary small-button">
                      Open workspace
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
