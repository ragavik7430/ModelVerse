"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  deleteDataset,
  getDataset,
  getProject,
  getStoredAuthToken,
  logout,
  type Dataset,
  type Project,
} from "@/lib/api";

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const formatPercent = (value: number): string => `${value.toFixed(1)}%`;

export default function DatasetDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string; datasetId: string }>();
  const projectId = Number(params.id);
  const datasetId = Number(params.datasetId);
  const [project, setProject] = useState<Project | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<"engineering" | "learning">("engineering");
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const load = async () => {
      try {
        const [projectResult, datasetResult] = await Promise.all([
          getProject(projectId),
          getDataset(datasetId),
        ]);
        setProject(projectResult);
        setDataset(datasetResult);
        setMode(projectResult.mode);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load dataset details.");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [datasetId, projectId, router]);

  const learningInsights = useMemo(() => {
    const summary = dataset?.summary;
    if (!summary) return [];

    return summary.columns.map((column) => {
      const missingPercent = summary.missing_percentages[column] ?? 0;
      const inferred = summary.inferred_types[column] ?? "categorical";
      const uniqueCount = summary.unique_value_counts[column] ?? 0;
      const description = missingPercent > 0
        ? `About ${Math.round(missingPercent)} out of every 100 records do not contain a value in ${column}. This may need to be handled before training.`
        : `The ${column} field is populated for most records. It appears to be ${inferred} and is in a usable shape for the next phase.`;

      return { name: column, description, uniqueCount };
    });
  }, [dataset]);

  const handleDelete = async () => {
    if (!dataset) return;
    const confirmed = window.confirm("Delete this dataset from the project?");
    if (!confirmed) return;

    try {
      await deleteDataset(dataset.id);
      router.push(`/projects/${projectId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete the dataset.");
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
    return <main className="auth-page"><div className="auth-card"><p className="auth-subtitle">Loading dataset details…</p></div></main>;
  }

  if (!dataset || !project) {
    return (
      <main className="auth-page">
        <div className="auth-card">
          <h1>Dataset unavailable</h1>
          <p className="auth-subtitle">{error || "This dataset could not be loaded."}</p>
          <Link href={`/projects/${projectId}`} className="button-primary auth-button">Back to project</Link>
        </div>
      </main>
    );
  }

  const summary = dataset.summary;

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Dataset navigation">
        <div className="brand">
          <span className="brand-mark">MV</span>
          <span className="brand-copy">
            <strong>ModelVerse</strong>
            <small>AI ENGINEERING WORKSPACE</small>
          </span>
        </div>

        <div className="workspace-label">DATASET</div>
        <nav className="nav-list">
          <Link href={`/projects/${project.id}`} className="nav-item">
            <span className="nav-marker" aria-hidden="true" />
            <span>Back to project</span>
          </Link>
          <span className="nav-item active">
            <span className="nav-marker" aria-hidden="true" />
            <span>{dataset.filename}</span>
          </span>
        </nav>

        <div className="sidebar-spacer" />
        <button type="button" className="button-secondary signout-button" onClick={handleLogout}>Sign out</button>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <span className="crumb">Workspace</span>
            <span className="crumb-slash">/</span>
            <Link href={`/projects/${project.id}`}>{project.name}</Link>
            <span className="crumb-slash">/</span>
            <strong>{dataset.filename}</strong>
          </div>
          <div className="topbar-right">
            <div className="mode-switch" role="group" aria-label="Dataset detail mode switch">
              <button type="button" className={mode === "engineering" ? "selected" : ""} onClick={() => setMode("engineering")} aria-pressed={mode === "engineering"}>Engineering</button>
              <button type="button" className={mode === "learning" ? "selected" : ""} onClick={() => setMode("learning")} aria-pressed={mode === "learning"}>Learning</button>
            </div>
          </div>
        </header>

        <main className="content project-detail-page">
          <div className="page-header-row">
            <div>
              <p className="section-kicker">DATASET</p>
              <h1>{dataset.filename}</h1>
              <p className="page-subtitle">Status: {dataset.status}</p>
            </div>
            <div className="inline-button-row">
              <Link href={`/projects/${project.id}`} className="button-secondary small-button">Back</Link>
              <button type="button" className="button-secondary small-button danger-button" onClick={handleDelete}>Delete dataset</button>
            </div>
          </div>

          {error ? <div className="error-box">{error}</div> : null}

          {summary ? (
            <>
              <div className="detail-grid dataset-overview-grid">
                <section className="project-detail-card">
                  <h2>Dataset overview</h2>
                  <div className="overview-list">
                    <div><span>Filename</span><strong>{dataset.filename}</strong></div>
                    <div><span>Size</span><strong>{formatFileSize(dataset.file_size)}</strong></div>
                    <div><span>Rows</span><strong>{summary.row_count}</strong></div>
                    <div><span>Columns</span><strong>{summary.column_count}</strong></div>
                    <div><span>File type</span><strong>{dataset.file_type}</strong></div>
                    <div><span>Status</span><strong>{dataset.status}</strong></div>
                    <div><span>Quality score</span><strong>{summary.quality_score}</strong></div>
                    <div><span>Quality status</span><strong>{summary.quality_status}</strong></div>
                  </div>
                </section>

                <section className="project-detail-card">
                  <h2>Data quality snapshot</h2>
                  <div className="quality-overview-list">
                    <div><span>Missing values</span><strong>{Object.values(summary.missing_values).reduce((sum, value) => sum + value, 0)}</strong></div>
                    <div><span>Duplicate rows</span><strong>{summary.duplicate_rows}</strong></div>
                    <div><span>Numeric columns</span><strong>{summary.numeric_columns.length}</strong></div>
                    <div><span>Categorical columns</span><strong>{summary.categorical_columns.length}</strong></div>
                    <div><span>Findings</span><strong>{summary.findings.length}</strong></div>
                  </div>
                </section>
              </div>

              {mode === "engineering" ? (
                <section className="project-detail-card wide-card">
                  <h2>Column overview</h2>
                  <div className="table-wrap">
                    <table className="dataset-table">
                      <thead>
                        <tr>
                          <th>Column</th>
                          <th>Type</th>
                          <th>Missing</th>
                          <th>Missing %</th>
                          <th>Unique</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.columns.map((column) => (
                          <tr key={column}>
                            <td>{column}</td>
                            <td>{summary.inferred_types[column] ?? "unknown"}</td>
                            <td>{summary.missing_values[column] ?? 0}</td>
                            <td>{formatPercent(summary.missing_percentages[column] ?? 0)}</td>
                            <td>{summary.unique_value_counts[column] ?? 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : (
                <section className="project-detail-card wide-card">
                  <h2>Plain-language explanations</h2>
                  <div className="learning-insights">
                    {learningInsights.map((item) => (
                      <div key={item.name} className="learning-card">
                        <strong>{item.name}</strong>
                        <p>{item.description}</p>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              <section className="project-detail-card wide-card">
                <h2>Quality findings</h2>
                {summary.findings.length === 0 ? (
                  <p className="empty-subcopy">No quality findings were detected for this dataset.</p>
                ) : (
                  <div className="findings-list">
                    {summary.findings.map((finding, index) => (
                      <div className="finding-card" key={`${finding.type}-${index}`}>
                        <span className={`severity-pill severity-${finding.severity}`}>{finding.severity}</span>
                        <div>
                          <h3>{finding.type.replace(/_/g, " ")}</h3>
                          <p>{finding.column ? `Column: ${finding.column}` : "Dataset-level issue"}</p>
                          <p>{finding.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
