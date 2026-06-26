/**
 * Frontend API client for the M7-B Agent Console.
 *
 * The console is **API-first**: clicking "generate" calls the local
 * FastAPI backend (M7-A) and renders the response. If the backend is
 * unavailable (not started, network error, non-2xx, invalid JSON),
 * every fetch function rejects with an `ApiError`; the page then
 * falls back to the static sample payloads.
 *
 * Boundaries (same as the rest of the project):
 *   - sample / simulation data only
 *   - no real NBA API, no LLM, no MCP
 *   - preview only — never approves or executes a transaction
 *   - no data writes
 *
 * No axios. Uses the native `fetch`. No new dependencies.
 *
 * Milestone: M7-B (Frontend API Integration).
 */

import type { DemoPayload } from "../data/demoProposalPayload";
import type { DemoTradePayload } from "../data/demoTradePreviewPayload";

// --------------------------------------------------------------------------- //
// Config
// --------------------------------------------------------------------------- //

/**
 * Base URL for the backend API.
 *
 * - In the browser, defaults to `http://127.0.0.1:8000` (the FastAPI
 *   dev server started by `uvicorn backend.app.api:app --reload`).
 * - Overridable via `NEXT_PUBLIC_API_BASE_URL` for non-default setups.
 * - Trailing slash is stripped so endpoint paths can be concatenated
 *   cleanly.
 */
export const API_BASE_URL: string = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

/**
 * Request timeout in milliseconds. If the backend takes longer than
 * this (including being unreachable), the fetch rejects and the page
 * falls back to static payloads. 8s is generous for a local dev server
 * that does deterministic, in-memory work.
 */
const REQUEST_TIMEOUT_MS = 8000;

// --------------------------------------------------------------------------- //
// Types
// --------------------------------------------------------------------------- //

/** Request body for POST /api/offseason/proposal-preview. */
export interface ProposalPreviewParams {
  team_id: string;
  objective: string;
  target_positions: string[];
  max_salary: number | null;
  max_candidates: number;
  evidence_query: string | null;
}

// --------------------------------------------------------------------------- //
// Agent trace types (M8-E3)
// --------------------------------------------------------------------------- //
//
// These mirror the additive `agent_trace` field returned by the backend
// on `/api/offseason/proposal-preview` and `/api/offseason/trade-preview-demo`
// (M8-E2). The field is OPTIONAL on both responses so that:
//   - older payloads without `agent_trace` still type-check
//   - the page can render a fallback card when the field is missing
//
// Boundary: the frontend only renders these structs — it never sends
// them to the backend, never mutates them, and never lets a step
// override the deterministic verdict from `validation_status`.

/** Status of a single trace step. Mirrors backend TraceStepStatus. */
export type AgentTraceStepStatus =
  | "pending"
  | "running"
  | "completed"
  | "warning"
  | "blocked";

/** A single step in the agent execution trace. */
export interface AgentTraceStep {
  step_id: string;
  sequence: number;
  status: AgentTraceStepStatus;
  title: string;
  plain_language_summary: string;
  tool_name: string;
  inputs_summary?: unknown;
  outputs_summary?: unknown;
  warnings?: string[];
  evidence_ids?: string[];
  requires_human_review?: boolean;
  technical_details?: Record<string, unknown>;
  started_at?: string | null;
  finished_at?: string | null;
}

/** Overall status of the agent trace. Mirrors TraceOverallStatus. */
export type AgentTraceOverallStatus =
  | "completed"
  | "warning"
  | "blocked"
  | "awaiting_human_approval";

/** Approval state reported by the trace. Mirrors ApprovalState. */
export type AgentTraceApprovalState =
  | "not_required"
  | "required"
  | "approved_preview"
  | "blocked";

/** Intent type reported by the trace. Mirrors TraceIntentType. */
export type AgentTraceIntentType =
  | "signing"
  | "trade"
  | "hold"
  | "compare";

/** The full agent trace envelope returned by the backend. */
export interface AgentTrace {
  run_id: string;
  intent_type: AgentTraceIntentType | string;
  overall_status: AgentTraceOverallStatus | string;
  current_state: string;
  data_source_label: string;
  steps: AgentTraceStep[];
  requires_human_approval: boolean;
  approval_state: AgentTraceApprovalState | string;
  final_message: string;
}

/**
 * Response shape for POST /api/offseason/proposal-preview.
 *
 * `agent_trace` is additive (M8-E2). The legacy fields come from
 * `DemoPayload`; the trace is layered on top as an optional key so
 * older payloads (and the local static fallback samples) still
 * type-check.
 */
export type ProposalPreviewResponse = DemoPayload & {
  agent_trace?: AgentTrace;
};

/**
 * Response shape for GET /api/offseason/trade-preview-demo.
 *
 * `agent_trace` is additive (M8-E2). The legacy fields come from
 * `DemoTradePayload`; the trace is layered on top as an optional key.
 */
export type TradePreviewDemoResponse = DemoTradePayload & {
  agent_trace?: AgentTrace;
};

/** Error thrown when the API call fails for any reason. */
export class ApiError extends Error {
  readonly kind:
    | "network"
    | "timeout"
    | "non-2xx"
    | "invalid-json"
    | "unknown";
  readonly status?: number;
  readonly url: string;

  constructor(
    kind: ApiError["kind"],
    message: string,
    url: string,
    status?: number,
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.url = url;
    this.status = status;
  }
}

// --------------------------------------------------------------------------- //
// Internal fetch wrapper
// --------------------------------------------------------------------------- //

/**
 * Fetch JSON from the backend with a timeout.
 *
 * Rejects with `ApiError` on any failure (network, timeout, non-2xx,
 * invalid JSON). Never throws a raw `Error` — callers can rely on
 * `instanceof ApiError` to decide fallback behavior.
 */
async function fetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  // Use AbortController for timeout so we don't hang forever when the
  // backend is down. The controller is local to this request.
  const controller =
    typeof AbortController !== "undefined" ? new AbortController() : null;
  const timeoutId =
    controller !== null
      ? setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
      : null;

  let resp: Response;
  try {
    resp = await fetch(url, {
      ...init,
      signal: controller?.signal,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch (err) {
    if (timeoutId) clearTimeout(timeoutId);
    // AbortError => timeout; everything else => network (backend down,
    // CORS preflight failed, DNS, etc.).
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("timeout", `request timed out after ${REQUEST_TIMEOUT_MS}ms`, url);
    }
    throw new ApiError(
      "network",
      `network error: ${err instanceof Error ? err.message : String(err)}`,
      url,
    );
  }

  if (timeoutId) clearTimeout(timeoutId);

  if (!resp.ok) {
    throw new ApiError(
      "non-2xx",
      `HTTP ${resp.status} ${resp.statusText}`,
      url,
      resp.status,
    );
  }

  try {
    return (await resp.json()) as T;
  } catch (err) {
    throw new ApiError(
      "invalid-json",
      `invalid JSON: ${err instanceof Error ? err.message : String(err)}`,
      url,
      resp.status,
    );
  }
}

// --------------------------------------------------------------------------- //
// Public API
// --------------------------------------------------------------------------- //

/**
 * POST /api/offseason/proposal-preview
 *
 * Generates an offseason proposal preview. `max_salary=20000000` yields
 * RECOMMENDED + SIGNING; `max_salary=15000000` yields NO_ACTION + HOLD.
 */
export async function fetchProposalPreview(
  params: ProposalPreviewParams,
): Promise<ProposalPreviewResponse> {
  return fetchJson<ProposalPreviewResponse>(
    "/api/offseason/proposal-preview",
    {
      method: "POST",
      body: JSON.stringify(params),
    },
  );
}

/**
 * GET /api/offseason/trade-preview-demo
 *
 * Returns the fixed demo two-team trade preview (DEM-ATL <-> DEM-PDX).
 */
export async function fetchTradePreviewDemo(): Promise<TradePreviewDemoResponse> {
  return fetchJson<TradePreviewDemoResponse>(
    "/api/offseason/trade-preview-demo",
  );
}

/**
 * GET /api/health
 *
 * Liveness probe + data source metadata. Optional — the page does not
 * require a health check before calling the data endpoints; it just
 * tries the data endpoint and falls back on failure. Exposed for
 * debugging / future use and for the data source status card (M8-D4).
 *
 * The legacy fields (status, sample_data, service) are always present.
 * M8-C1/C2 added additive data source metadata that may be null when
 * running in demo mode. We read them as optional so the type reflects
 * the real backend contract.
 */
export interface HealthResponse {
  // Legacy fields (always present)
  status: string;
  sample_data: boolean;
  service: string;
  // Additive data source metadata (M8-C1/C2). Null in demo mode.
  data_mode?: string | null;
  active_data_source?: string | null;
  snapshot_id?: string | null;
  snapshot_valid?: boolean | null;
  snapshot_is_fixture?: boolean | null;
  snapshot_type?: string | null;
  snapshot_warnings?: string[] | null;
  fallback_reason?: string | null;
  strict_snapshot?: boolean | null;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return fetchJson("/api/health");
}

// --------------------------------------------------------------------------- //
// Demo request presets
// --------------------------------------------------------------------------- //

/**
 * The three demo request presets used by the Agent Console. Kept here
 * so the page logic stays declarative and the presets are easy to audit
 * in one place.
 *
 * These mirror the `example_request` values advertised by
 * GET /api/offseason/scenarios.
 */
export const DEMO_PROPOSAL_REQUESTS = {
  signing: {
    team_id: "DEM-ATL",
    objective: "Add frontcourt help",
    target_positions: ["C"],
    max_salary: 20000000,
    max_candidates: 2,
    evidence_query: "center need cap flexibility",
  },
  hold: {
    team_id: "DEM-ATL",
    objective: "Add frontcourt help",
    target_positions: ["C"],
    max_salary: 15000000,
    max_candidates: 2,
    evidence_query: "center need cap flexibility",
  },
} as const satisfies Record<"signing" | "hold", ProposalPreviewParams>;
