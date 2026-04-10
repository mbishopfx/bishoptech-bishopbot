import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BISHOP_DASHBOARD_API_URL ?? "http://127.0.0.1:8080";
const API_TOKEN = process.env.BISHOP_DASHBOARD_API_TOKEN ?? "";

function buildBackendUrl(path: string[], request: NextRequest) {
  const url = new URL(`/api/dashboard/${path.join("/")}`, BACKEND_URL);
  request.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });
  return url;
}

async function proxy(request: NextRequest, path: string[]) {
  const headers = new Headers();
  headers.set("Accept", "application/json");
  if (API_TOKEN) {
    headers.set("X-Bishop-Dashboard-Token", API_TOKEN);
  }
  if (request.method !== "GET") {
    headers.set("Content-Type", "application/json");
  }

  try {
    const response = await fetch(buildBackendUrl(path, request), {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.text(),
      cache: "no-store",
    });

    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Dashboard backend is unavailable.",
        detail: error instanceof Error ? error.message : "Unknown fetch error",
      },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}
