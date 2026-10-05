"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import {
  deleteDataset,
  createExperiment,
  getProject,
  getProjectExperiments,
  getExperimentComparison,
  getProjectDatasets,
  getStoredAuthToken,
  logout,
  optimizeExperiment,
  recommendProjectPipeline,
  trainExperiment,
  updateProject,
  uploadDataset,
  type Dataset,
  type Experiment,
  type ExperimentComparison,
  type ProblemType,
  type PipelineRecommendation,
  type Project,
} from "@/lib/api";

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const supportedAlgorithms = new Set([
  "Logistic Regression",
  "Random Forest",
  "Gradient Boosting",
  "Linear Regression",
  "Random Forest Regressor",
  "Gradient Boosting Regressor",
  "K-Means",
]);

const isIdentifierLike = (column: string): boolean => {
  const normalized = column.replace(/([a-z0-9])([A-Z])/g, "$1_$2").replace(/[-\s]/g, "_").toLowerCase();
  return ["id", "uuid", "index", "identifier", "key"].includes(normalized) ||
    normalized.startsWith("id_") || /_(id|uuid|index|identifier)$/.test(normalized);
};

const isProblemType = (value: string): value is ProblemType =>
  value === "regression" || value === "classification" || value === "clustering";

const formatMetric = (value: unknown): string =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(4) : "N/A";

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
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedExperimentId, setSelectedExperimentId] = useState<number | null>(null);
  const [comparison, setComparison] = useState<ExperimentComparison | null>(null);
  const [selectedAlgorithms, setSelectedAlgorithms] = useState<string[]>([]);
  const [targetColumn, setTargetColumn] = useState("");
  const [targetConfirmed, setTargetConfirmed] = useState(false);
  const [allowIdentifierTarget, setAllowIdentifierTarget] = useState(false);
  const [testSize, setTestSize] = useState(0.2);
  const [randomState, setRandomState] = useState(42);
  const [optimizeTraining, setOptimizeTraining] = useState(false);
  const [training, setTraining] = useState(false);
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
        const [projectResult, datasetList, experimentList] = await Promise.all([
          getProject(projectId),
          getProjectDatasets(projectId),
          getProjectExperiments(projectId),
        ]);
        setProject(projectResult);
        setDatasets(datasetList);
        setExperiments(experimentList);
        if (experimentList.length > 0) {
          setSelectedExperimentId(experimentList[0].id);
          setComparison(await getExperimentComparison(experimentList[0].id));
        }
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
      setSelectedAlgorithms(result.candidate_algorithms.filter((algorithm) => supportedAlgorithms.has(algorithm)));
      setTargetColumn("");
      setTargetConfirmed(false);
      setAllowIdentifierTarget(false);
    } catch (err) {
      setRecommendation(null);
      setError(err instanceof Error ? err.message : "Unable to generate a pipeline recommendation.");
    } finally {
      setAnalyzingRecommendation(false);
    }
  };

  const handleTraining = async () => {
    if (!project || !recommendation || !isProblemType(recommendation.problem_type)) {
      setError("Run a supported Phase 4 recommendation before creating a training experiment.");
      return;
    }
    if (selectedAlgorithms.length === 0) {
      setError("Select at least one supported algorithm from the Phase 4 recommendation.");
      return;
    }
    if (recommendation.problem_type !== "clustering" && (!targetColumn || !targetConfirmed)) {
      setError("Select and explicitly confirm a target column before training.");
      return;
    }

    try {
      setTraining(true);
      setError("");
      const experiment = await createExperiment(project.id, {
        dataset_id: recommendation.dataset_id,
        problem_type: recommendation.problem_type,
        target_column: recommendation.problem_type === "clustering" ? null : targetColumn,
        target_confirmed: recommendation.problem_type === "clustering" ? false : targetConfirmed,
        allow_identifier_target: allowIdentifierTarget,
        selected_algorithms: selectedAlgorithms,
        test_size: testSize,
        random_state: randomState,
        optimize: optimizeTraining,
      });
      const result = optimizeTraining
        ? await optimizeExperiment(experiment.id)
        : await trainExperiment(experiment.id);
      setExperiments((current) => [result, ...current.filter((item) => item.id !== result.id)]);
      setSelectedExperimentId(result.id);
      setComparison(await getExperimentComparison(result.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to complete the training experiment.");
    } finally {
      setTraining(false);
    }
  };

  const handleSelectExperiment = async (experimentId: number) => {
    try {
      setError("");
      setSelectedExperimentId(experimentId);
      setComparison(await getExperimentComparison(experimentId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load the model comparison.");
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

  const datasetColumns = Array.isArray(recommendation?.dataset_summary.columns)
    ? recommendation.dataset_summary.columns.filter((column): column is string => typeof column === "string")
    : [];
  const selectedExperiment = experiments.find((experiment) => experiment.id === selectedExperimentId) ?? null;
  const comparisonCandidates = comparison?.candidates ?? selectedExperiment?.models ?? [];

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

            <section className="project-detail-card wide-card" aria-labelledby="training-heading">
              <div className="section-header-row">
                <div>
                  <p className="section-kicker">PHASE 5</p>
                  <h2 id="training-heading">ML Training &amp; Experimentation</h2>
                </div>
                <span className="dataset-pill">{experiments.length} saved experiments</span>
              </div>

              <p className="training-intro">
                Review a fresh Phase 4 recommendation, confirm the training target, then compare reproducible model runs.
                Recommendations remain on-demand; completed experiment results are saved in this workspace.
              </p>

              {!recommendation ? (
                <div className="empty-state compact">
                  <h3>Review a pipeline recommendation first</h3>
                  <p>Run “Analyze &amp; Recommend” above to load the current candidate algorithms and dataset profile. Previous experiment history remains available below.</p>
                </div>
              ) : (
                <div className="training-form">
                  <div className="training-config-grid">
                    <div className="field">
                      <span>Dataset</span>
                      <strong>{datasets.find((dataset) => dataset.id === recommendation.dataset_id)?.filename ?? `Dataset ${recommendation.dataset_id}`}</strong>
                    </div>
                    <div className="field">
                      <span>Recommended problem type</span>
                      <strong>{recommendation.problem_type}</strong>
                    </div>
                  </div>

                  {recommendation.problem_type === "unknown" ? (
                    <div className="error-box">Phase 4 could not determine a supported problem type. Update the problem definition and request a new recommendation before training.</div>
                  ) : null}

                  {recommendation.problem_type !== "clustering" && isProblemType(recommendation.problem_type) ? (
                    <div className="training-config-grid">
                      <label className="field">
                        <span>Confirm target column</span>
                        <select value={targetColumn} onChange={(event) => { setTargetColumn(event.target.value); setTargetConfirmed(false); setAllowIdentifierTarget(false); }}>
                          <option value="">Select the target explicitly</option>
                          {datasetColumns.map((column) => <option key={column} value={column}>{column}</option>)}
                        </select>
                      </label>
                      <label className="training-check">
                        <input type="checkbox" checked={targetConfirmed} disabled={!targetColumn} onChange={(event) => setTargetConfirmed(event.target.checked)} />
                        <span>I reviewed and confirm this is the target the model should learn to predict.</span>
                      </label>
                    </div>
                  ) : null}

                  {targetColumn && isIdentifierLike(targetColumn) ? (
                    <label className="training-check warning-check">
                      <input type="checkbox" checked={allowIdentifierTarget} onChange={(event) => setAllowIdentifierTarget(event.target.checked)} />
                      <span>Allow this identifier-like target only if predicting identifiers is intentional.</span>
                    </label>
                  ) : null}

                  <fieldset className="training-algorithms">
                    <legend>Candidate algorithms from the Phase 4 recommendation</legend>
                    {recommendation.candidate_algorithms.filter((algorithm) => supportedAlgorithms.has(algorithm)).length === 0 ? (
                      <p>No Phase 4 candidate is currently supported by the Phase 5 training registry.</p>
                    ) : (
                      <div className="training-algorithm-list">
                        {recommendation.candidate_algorithms.filter((algorithm) => supportedAlgorithms.has(algorithm)).map((algorithm) => (
                          <label className="training-check" key={algorithm}>
                            <input
                              type="checkbox"
                              checked={selectedAlgorithms.includes(algorithm)}
                              onChange={(event) => setSelectedAlgorithms((current) => event.target.checked
                                ? [...current, algorithm]
                                : current.filter((item) => item !== algorithm))}
                            />
                            <span>{algorithm}</span>
                          </label>
                        ))}
                      </div>
                    )}
                    {recommendation.candidate_algorithms.some((algorithm) => !supportedAlgorithms.has(algorithm)) ? (
                      <p className="training-note">Some recommended candidates are not in the initial Phase 5 registry and cannot be selected.</p>
                    ) : null}
                  </fieldset>

                  <div className="training-config-grid">
                    <label className="field">
                      <span>Test data held out</span>
                      <select value={testSize} onChange={(event) => setTestSize(Number(event.target.value))}>
                        <option value={0.2}>20%</option>
                        <option value={0.25}>25%</option>
                        <option value={0.3}>30%</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Reproducible random seed</span>
                      <input type="number" min={0} max={2147483647} value={randomState} onChange={(event) => setRandomState(Number(event.target.value))} />
                    </label>
                  </div>

                  <label className="training-check">
                    <input type="checkbox" checked={optimizeTraining} onChange={(event) => setOptimizeTraining(event.target.checked)} />
                    <span>Run bounded Optuna hyperparameter optimization before final evaluation.</span>
                  </label>
                  <p className="training-note">Preprocessing is fitted on training data only. The test split is held out for final metrics; tuning uses validation data.</p>

                  <button
                    type="button"
                    className="button-primary"
                    onClick={() => void handleTraining()}
                    disabled={training || !isProblemType(recommendation.problem_type)}
                  >
                    {training ? "Training in progress..." : optimizeTraining ? "Create & optimize experiment" : "Create & train experiment"}
                  </button>
                </div>
              )}

              {training ? <p className="training-note" role="status">The backend is training the selected candidates. This button state ends when the actual run response arrives; no simulated progress is shown.</p> : null}

              <div className="experiment-history">
                <h3>Experiment history</h3>
                {experiments.length === 0 ? (
                  <div className="empty-state compact"><p>No saved experiments yet.</p></div>
                ) : (
                  <div className="experiment-history-list">
                    {experiments.map((experiment) => (
                      <button
                        type="button"
                        key={experiment.id}
                        className={`experiment-history-item ${selectedExperimentId === experiment.id ? "selected" : ""}`}
                        onClick={() => void handleSelectExperiment(experiment.id)}
                      >
                        <span><strong>Experiment {experiment.id}</strong><small>{experiment.problem_type} · {experiment.target_column ?? "no target"}</small></span>
                        <span className={`experiment-status status-${experiment.status}`}>{experiment.status}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {selectedExperiment ? (
                <div className="experiment-results">
                  <div className="section-header-row">
                    <h3>{selectedExperiment.experiment_name}</h3>
                    <span className={`experiment-status status-${selectedExperiment.status}`}>{selectedExperiment.status}</span>
                  </div>
                  <p>Experiment ID: {selectedExperiment.id} · Dataset ID: {selectedExperiment.dataset_id ?? String(selectedExperiment.configuration.dataset_id_snapshot ?? "deleted")} · Created {new Date(selectedExperiment.created_at).toLocaleString()}</p>
                  <p>Problem: {selectedExperiment.problem_type} · Target: {selectedExperiment.target_column ?? "none"} · Random seed: {selectedExperiment.random_state} · Test split: {(selectedExperiment.test_size * 100).toFixed(0)}%</p>
                  {selectedExperiment.error_message ? <div className="error-box">{selectedExperiment.error_message}</div> : null}
                  {selectedExperiment.comparison_policy ? <p><strong>Best-candidate policy:</strong> {selectedExperiment.comparison_policy}</p> : null}
                  {selectedExperiment.best_model_id ? (
                    <p className="best-candidate"><strong>Best candidate:</strong> {comparisonCandidates.find((model) => model.id === selectedExperiment.best_model_id)?.algorithm ?? `Model ${selectedExperiment.best_model_id}`}</p>
                  ) : null}
                  {comparisonCandidates.length === 0 ? <p>No candidate model results are available for this experiment.</p> : (
                    <div className="experiment-model-list">
                      {comparisonCandidates.map((model) => {
                        const testMetrics = model.metrics.test && typeof model.metrics.test === "object"
                          ? model.metrics.test as Record<string, unknown>
                          : {};
                        const trainMetrics = model.metrics.train && typeof model.metrics.train === "object"
                          ? model.metrics.train as Record<string, unknown>
                          : {};
                        const validationMetrics = model.metrics.validation && typeof model.metrics.validation === "object"
                          ? model.metrics.validation as Record<string, unknown>
                          : {};
                        const optimization = model.metrics.optimization && typeof model.metrics.optimization === "object"
                          ? model.metrics.optimization as Record<string, unknown>
                          : null;
                        return (
                          <article className="experiment-model-card" key={model.id}>
                            <div className="section-header-row">
                              <h4>{model.algorithm}</h4>
                              <span className={`experiment-status status-${model.status}`}>{model.status}</span>
                            </div>
                            {model.error_message ? <p className="error-box">{model.error_message}</p> : null}
                            {model.status === "completed" ? (
                              <>
                                <div className="metric-split-grid">
                                  {[
                                    ["Train", trainMetrics],
                                    ["Validation", validationMetrics],
                                    ["Test", testMetrics],
                                  ].map(([label, values]) => (
                                    <div className="metric-split" key={label as string}>
                                      <strong>{label as string} metrics</strong>
                                      {Object.entries(values as Record<string, unknown>)
                                        .filter(([, value]) => typeof value === "number" || value === null)
                                        .map(([name, value]) => <span key={name}>{name}: {formatMetric(value)}</span>)}
                                    </div>
                                  ))}
                                </div>
                                {testMetrics.confusion_matrix ? <details><summary>Test confusion matrix</summary><pre>{JSON.stringify(testMetrics.confusion_matrix, null, 2)}</pre></details> : null}
                                {optimization ? <p><strong>Optuna result:</strong> objective {formatMetric(optimization.best_objective)} · trials {String(optimization.n_trials)} · parameters {JSON.stringify(optimization.best_parameters)}</p> : null}
                                <p className="engineering-detail"><strong>MLflow run ID:</strong> {model.mlflow_run_id ?? "not available"}</p>
                                {project.mode === "engineering" ? (
                                  <>
                                    <details><summary>Model parameters</summary><pre>{JSON.stringify(model.parameters, null, 2)}</pre></details>
                                    <details><summary>Preprocessing configuration</summary><pre>{JSON.stringify(model.preprocessing, null, 2)}</pre></details>
                                  </>
                                ) : (
                                  <p className="learning-explanation">
                                    Training learns patterns from the training split. Validation metrics guided candidate selection; the test metrics above were calculated on the held-out split.{" "}
                                    {selectedExperiment.problem_type === "regression"
                                      ? "For regression, lower MAE/RMSE is better and R² summarizes variance explained."
                                      : selectedExperiment.problem_type === "classification"
                                        ? "For classification, higher accuracy and macro F1 indicate stronger overall class prediction."
                                        : "For clustering, silhouette summarizes how separated the generated groups are; higher values indicate better separation."}{" "}
                                    These values come from this experiment’s actual predictions.
                                  </p>
                                )}
                              </>
                            ) : null}
                          </article>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : null}
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
