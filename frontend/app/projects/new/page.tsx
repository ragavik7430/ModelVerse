"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { createProject, getStoredAuthToken } from "@/lib/api";

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [problemStatement, setProblemStatement] = useState("");
  const [objective, setObjective] = useState("");
  const [mode, setMode] = useState<"engineering" | "learning">("engineering");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getStoredAuthToken()) {
      router.replace("/login");
    }
  }, [router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const project = await createProject({
        name: name.trim(),
        problem_statement: problemStatement.trim(),
        objective: objective.trim(),
        mode,
      });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create the project.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <div className="auth-card form-card wide-form">
        <div className="brand-row">
          <span className="brand-mark">MV</span>
          <div>
            <strong>ModelVerse</strong>
            <small>AI ENGINEERING WORKSPACE</small>
          </div>
        </div>

        <div className="auth-header form-header">
          <h1>Create a new project</h1>
        </div>

        {error ? <div className="error-box">{error}</div> : null}

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Project Name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Customer churn forecast" required />
          </label>

          <label className="field">
            <span>Problem Statement</span>
            <textarea
              value={problemStatement}
              onChange={(event) => setProblemStatement(event.target.value)}
              placeholder="Describe the real problem you want to solve."
              rows={5}
              required
            />
          </label>

          <label className="field">
            <span>Objective</span>
            <textarea
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              placeholder="What success looks like for this workspace."
              rows={4}
              required
            />
          </label>

          <label className="field">
            <span>Mode</span>
            <select value={mode} onChange={(event) => setMode(event.target.value as "engineering" | "learning")}>
              <option value="engineering">Engineering</option>
              <option value="learning">Learning</option>
            </select>
          </label>

          <button type="submit" className="button-primary auth-button" disabled={submitting}>
            {submitting ? "Creating project..." : "Create Project"}
          </button>
        </form>
      </div>
    </main>
  );
}
