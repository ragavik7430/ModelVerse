"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import {
  deleteDataset,
  getProject,
  getProjectDatasets,
  getStoredAuthToken,
  logout,
  recommendProjectPipeline,
  updateProject,
  uploadDataset,
  type Dataset,
  type PipelineRecommendation,
  type Project,
} from "@/lib/api";

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

export default function ProjectDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingProject, setSavingProject] = useState(false);
  const [uploadingDataset, setUploadingDataset] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [recommendation, setRecommendation] = useState<PipelineRecommendation | null>(null);
  const [analyzingRecommendation, setAnalyzingRecommendation] = useState(false);
  const [error, setError] = useState("");
  const [projectForm, setProjectForm] = useState({
    name: "",
    problem_statement: "",
    objective: "",
    mode: "engineering" as "engineering" | "learning",
  });

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const load = async () => {
      try {
        const [projectResult, datasetList] = await Promise.all([
          getProject(projectId),
          getProjectDatasets(projectId),
        ]);
        setProject(projectResult);
        setDatasets(datasetList);
        setProjectForm({
          name: projectResult.name,
          problem_statement: projectResult.problem_statement,
          objective: projectResult.objective,
          mode: projectResult.mode,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load project workspace.");
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
      setProjectForm((current) => ({ ...current, mode }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update the workspace mode.");
    }
  };

  const handleProjectSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!project) return;

    try {
      setSavingProject(true);
      const updated = await updateProject(project.id, projectForm);
      setProject(updated);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the project problem definition.");
    } finally {
      setSavingProject(false);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !project) return;

    try {
      setUploadingDataset(true);
      setError("");
      const uploaded = await uploadDataset(project.id, selectedFile);
      setDatasets((current) => [uploaded, ...current]);
      setSelectedFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload the dataset.");
    } finally {
      setUploadingDataset(false);
    }
  };

  const handleDeleteDataset = async (datasetId: number) => {
    const confirmed = window.confirm("Delete this dataset from the project workspace?");
    if (!confirmed) return;

    try {
      await deleteDataset(datasetId);
      setDatasets((current) => current.filter((dataset) => dataset.id !== datasetId));
      setRecommendation(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete the dataset.");
    }
  };

  const handleAnalyzeRecommendation = async () => {
    if (!project) return;
    if (datasets.length === 0) {
      setRecommendation(null);
      setError("Add a dataset before requesting an AI pipeline recommendation.");
      return;
    }

    try {
      setAnalyzingRecommendation(true);
      setError("");
      const result = await recommendProjectPipeline(project.id);
      setRecommendation(result);
    } catch (err) {
      setRecommendation(null);
      setError(err instanceof Error ? err.message : "Unable to generate a pipeline recommendation.");
    } finally {
      setAnalyzingRecommendation(false);
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
            <section className="project-detail-card wide-card">
              <div className="section-header-row">
                <h2>Problem Definition</h2>
              </div>

              <form id="project-problem-form" className="workspace-form" onSubmit={handleProjectSave}>
                <label className="field">
                  <span>Project Name</span>
                  <input
                    value={projectForm.name}
                    onChange={(event) => setProjectForm((current) => ({ ...current, name: event.target.value }))}
                  />
                </label>

                <label className="field">
                  <span>Problem Statement</span>
                  <textarea
                    rows={5}
                    value={projectForm.problem_statement}
                    onChange={(event) => setProjectForm((current) => ({ ...current, problem_statement: event.target.value }))}
                  />
                </label>

                <label className="field">
                  <span>Objective</span>
                  <textarea
                    rows={4}
                    value={projectForm.objective}
                    onChange={(event) => setProjectForm((current) => ({ ...current, objective: event.target.value }))}
                  />
                </label>

                <label className="field">
                  <span>Workspace Mode</span>
                  <select
                    value={projectForm.mode}
                    onChange={(event) => setProjectForm((current) => ({ ...current, mode: event.target.value as "engineering" | "learning" }))}
                  >
                    <option value="engineering">Engineering</option>
                    <option value="learning">Learning</option>
                  </select>
                </label>

                <button type="submit" className="button-primary" disabled={savingProject}>
                  {savingProject ? "Saving changes..." : "Save problem details"}
                </button>
              </form>
            </section>

            <section className="project-detail-card wide-card">
              <div className="section-header-row">
                <h2>Dataset Intelligence</h2>
              </div>

              <div className="dataset-upload-row">
                <input
                  type="file"
                  accept=".csv,text/csv,application/csv"
                  onChange={(event: ChangeEvent<HTMLInputElement>) => setSelectedFile(event.target.files?.[0] ?? null)}
                />
                <button type="button" className="button-primary small-button" onClick={() => void handleUpload()} disabled={!selectedFile || uploadingDataset}>
                  {uploadingDataset ? "Uploading..." : "Upload Dataset"}
                </button>
              </div>

              {datasets.length === 0 ? (
                <div className="empty-state compact">
                  <h3>No datasets uploaded yet</h3>
                  <p>Upload a real CSV and ModelVerse will analyze quality, completeness, and readiness.</p>
                </div>
              ) : (
                <div className="dataset-list">
                  {datasets.map((dataset) => (
                    <article key={dataset.id} className="dataset-card">
                      <div className="dataset-card-header">
                        <div>
                          <strong>{dataset.filename}</strong>
                          <small>{dataset.status}</small>
                        </div>
                        <span className="dataset-pill">{dataset.row_count} rows</span>
                      </div>
                      <div className="dataset-meta-grid">
                        <span>Size: {formatFileSize(dataset.file_size)}</span>
                        <span>Cols: {dataset.column_count}</span>
                        <span>Uploaded: {new Date(dataset.uploaded_at).toLocaleDateString()}</span>
                      </div>
                      <div className="dataset-actions">
                        <Link href={`/projects/${project.id}/datasets/${dataset.id}`} className="button-secondary small-button">
                          View dataset
                        </Link>
                        <button type="button" className="button-secondary small-button danger-button" onClick={() => void handleDeleteDataset(dataset.id)}>
                          Delete
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="project-detail-card wide-card">
              <div className="section-header-row">
                <h2>AI Pipeline Recommendation</h2>
                <button type="button" className="button-primary small-button" onClick={() => void handleAnalyzeRecommendation()} disabled={analyzingRecommendation || datasets.length === 0}>
                  {analyzingRecommendation ? "Analyzing..." : "Analyze & Recommend"}
                </button>
              </div>

              {datasets.length === 0 ? (
                <div className="empty-state compact">
                  <h3>No dataset available</h3>
                  <p>Upload a dataset to run the agentic pipeline analysis.</p>
                </div>
              ) : recommendation ? (
                <div className="recommendation-panel">
                  <div className="recommendation-summary">
                    <div>
                      <span className="section-kicker">Problem type</span>
                      <h3>{recommendation.problem_type}</h3>
                    </div>
                    <div>
                      <span className="section-kicker">Confidence</span>
                      <h3>{recommendation.confidence.toFixed(2)}</h3>
                    </div>
                  </div>

                  <div className="detail-grid recommendation-grid">
                    <div className="project-detail-card">
                      <h4>Recommended pipeline</h4>
                      <p>{recommendation.recommended_pipeline}</p>
                      <ul>
                        {recommendation.candidate_algorithms.length > 0 ? (
                          recommendation.candidate_algorithms.map((algorithm) => <li key={algorithm}>{algorithm}</li>)
                        ) : (
                          <li>No candidate algorithms could be inferred.</li>
                        )}
                      </ul>
                    </div>

                    <div className="project-detail-card">
                      <h4>Preprocessing</h4>
                      <ul>
                        {recommendation.preprocessing_steps.length > 0 ? (
                          recommendation.preprocessing_steps.map((step) => <li key={step}>{step}</li>)
                        ) : (
                          <li>No preprocessing steps flagged.</li>
                        )}
                      </ul>
                    </div>
                  </div>

                  <div className="project-detail-card">
                    <h4>{project.mode === "learning" ? "Plain-language explanation" : "Technical rationale"}</h4>
                    <p>{project.mode === "learning" ? recommendation.explanation : recommendation.rationale}</p>
                    <p><strong>Recommendation rationale:</strong> {recommendation.rationale}</p>
                    <p><strong>Warnings:</strong> {recommendation.warnings.length > 0 ? recommendation.warnings.join("; ") : "None"}</p>
                    <p><strong>Needs review:</strong> {recommendation.warnings.length > 0 ? recommendation.warnings.join("; ") : "Target definition and final pipeline selection."}</p>
                  </div>
                </div>
              ) : (
                <div className="empty-state compact">
                  <h3>Analysis not run</h3>
                  <p>Use the action above to generate a pipeline recommendation based on the project problem and dataset quality.</p>
                </div>
              )}
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
