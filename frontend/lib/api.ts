export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export type HealthResponse = { status: string; service?: string; version?: string; message?: string };
export type HealthCheckResult =
  | { available: true; data: HealthResponse }
  | { available: false; message: string };

export type AuthUser = {
  id: number;
  email: string;
  created_at: string;
};

export type AuthToken = {
  access_token: string;
  token_type: string;
};

export type Project = {
  id: number;
  user_id: number;
  name: string;
  problem_statement: string;
  objective: string;
  mode: "engineering" | "learning";
  status: string;
  created_at: string;
  updated_at: string;
};

export type DatasetSummary = {
  row_count: number;
  column_count: number;
  columns: string[];
  missing_values: Record<string, number>;
  missing_percentages: Record<string, number>;
  duplicate_rows: number;
  duplicate_percentage: number;
  unique_value_counts: Record<string, number>;
  numeric_columns: string[];
  categorical_columns: string[];
  inferred_types: Record<string, string>;
  quality_score: number;
  quality_status: string;
  findings: Array<{
    type: string;
    severity: "info" | "warning" | "error";
    column?: string | null;
    message: string;
    value: number | string | null;
  }>;
};

export type Dataset = {
  id: number;
  project_id: number;
  filename: string;
  original_filename: string;
  file_size: number;
  file_type: string;
  row_count: number;
  column_count: number;
  status: string;
  uploaded_at: string;
  updated_at: string;
  summary?: DatasetSummary;
};

const STORAGE_KEY = "modelverse_token";
const HEALTH_ENDPOINT = "/system/health";

export function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEY);
}

export function setStoredAuthToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, token);
}

export function clearStoredAuthToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}

function isHealthResponse(data: unknown): data is HealthResponse {
  return typeof data === "object" && data !== null &&
    "status" in data && typeof data.status === "string" && data.status.length > 0 &&
    (!("service" in data) || typeof data.service === "string") &&
    (!("version" in data) || typeof data.version === "string") &&
    (!("message" in data) || typeof data.message === "string");
}

async function apiRequest<T>(path: string, options: RequestInit = {}, requireAuth = false): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const token = getStoredAuthToken();
  if (requireAuth && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (response.status === 401 && typeof window !== "undefined") {
    clearStoredAuthToken();
  }

  if (!response.ok) {
    let message = "Request failed.";
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      message = `Request failed with status ${response.status}.`;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export async function fetchHealth(): Promise<HealthCheckResult> {
  try {
    const res = await fetch(`${API_BASE_URL}${HEALTH_ENDPOINT}`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
    if (!res.ok) return { available: false, message: `Health check request returned HTTP ${res.status}.` };
    const result: unknown = await res.json();
    if (typeof result !== "object" || result === null || !("status" in result)) {
      return { available: false, message: "The health response was invalid." };
    }
    const health = result as HealthResponse;
    if (isHealthResponse(health)) {
      return { available: true, data: health };
    }
    return { available: false, message: "The health response was invalid." };
  } catch {
    return { available: false, message: "Could not connect to backend." };
  }
}

export async function register(payload: { email: string; password: string }): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  }, false);
}

export async function login(payload: { email: string; password: string }): Promise<AuthToken> {
  const result = await apiRequest<AuthToken>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  }, false);
  setStoredAuthToken(result.access_token);
  return result;
}

export async function logout(): Promise<void> {
  const token = getStoredAuthToken();
  try {
    if (token) {
      await apiRequest<{ detail: string }>("/auth/logout", { method: "POST" }, true);
    }
  } finally {
    clearStoredAuthToken();
  }
}

export async function getCurrentUser(): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/me", { method: "GET" }, true);
}

export async function getProjects(): Promise<Project[]> {
  return apiRequest<Project[]>("/projects", { method: "GET" }, true);
}

export async function getProject(projectId: number): Promise<Project> {
  return apiRequest<Project>(`/projects/${projectId}`, { method: "GET" }, true);
}

export async function createProject(payload: {
  name: string;
  problem_statement: string;
  objective: string;
  mode: "engineering" | "learning";
}): Promise<Project> {
  return apiRequest<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  }, true);
}

export async function updateProject(projectId: number, payload: Partial<Project>): Promise<Project> {
  return apiRequest<Project>(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }, true);
}

export async function deleteProject(projectId: number): Promise<{ deleted: boolean; project_id: number }> {
  return apiRequest<{ deleted: boolean; project_id: number }>(`/projects/${projectId}`, {
    method: "DELETE",
  }, true);
}

export async function getProjectDatasets(projectId: number): Promise<Dataset[]> {
  return apiRequest<Dataset[]>(`/projects/${projectId}/datasets`, { method: "GET" }, true);
}

export async function getDataset(datasetId: number): Promise<Dataset> {
  return apiRequest<Dataset>(`/datasets/${datasetId}`, { method: "GET" }, true);
}

export async function uploadDataset(projectId: number, file: File): Promise<Dataset> {
  const formData = new FormData();
  formData.append("file", file);

  const token = getStoredAuthToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/datasets`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (response.status === 401 && typeof window !== "undefined") {
    clearStoredAuthToken();
  }

  if (!response.ok) {
    let message = "Dataset upload failed.";
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      message = `Dataset upload failed with status ${response.status}.`;
    }
    throw new Error(message);
  }

  return response.json() as Promise<Dataset>;
}

export async function deleteDataset(datasetId: number): Promise<{ deleted: boolean; dataset_id: number }> {
  return apiRequest<{ deleted: boolean; dataset_id: number }>(`/datasets/${datasetId}`, {
    method: "DELETE",
  }, true);
}
