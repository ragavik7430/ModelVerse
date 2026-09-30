export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export type HealthResponse = { status: string; service?: string; version?: string; message?: string };
export type HealthCheckResult =
  | { available: true; data: HealthResponse }
  | { available: false; message: string };

const HEALTH_ENDPOINT = "/api/system/health";

function isHealthResponse(data: unknown): data is HealthResponse {
  return typeof data === "object" && data !== null &&
    "status" in data && typeof data.status === "string" && data.status.length > 0 &&
    (!("service" in data) || typeof data.service === "string") &&
    (!("version" in data) || typeof data.version === "string") &&
    (!("message" in data) || typeof data.message === "string");
}

export async function fetchHealth(): Promise<HealthCheckResult> {
  try {
    const res = await fetch(HEALTH_ENDPOINT, { cache: "no-store", signal: AbortSignal.timeout(5000) });
    if (!res.ok) return { available: false, message: `Health check request returned HTTP ${res.status}.` };
    const result: unknown = await res.json();
    if (typeof result !== "object" || result === null || !("available" in result)) {
      return { available: false, message: "The health response was invalid." };
    }
    if (result.available === false && "message" in result && typeof result.message === "string") {
      return { available: false, message: result.message };
    }
    if (result.available === true && "data" in result && isHealthResponse(result.data)) {
      return { available: true, data: result.data };
    }
    return { available: false, message: "The health response was invalid." };
  } catch {
    return { available: false, message: "Could not connect to backend." };
  }
}
