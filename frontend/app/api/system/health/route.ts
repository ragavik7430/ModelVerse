import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api";

export async function GET() {
  try {
    const response = await fetch(`${API_BASE_URL}/system/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      return NextResponse.json({
        available: false,
        message: `Health check returned HTTP ${response.status}.`,
      });
    }

    return NextResponse.json({ available: true, data: await response.json() });
  } catch {
    return NextResponse.json({ available: false, message: "Could not connect to backend." });
  }
}