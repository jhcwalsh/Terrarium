/**
 * Session-service client (su-app-02; DN-3 W5).
 *
 * Everything that scores round-trips the server: the reveal pointer during
 * play, decisions, completion, the outcome. This module is a thin, typed
 * fetch wrapper over ah.serve — it holds NO game logic, because the server
 * refusing an illegal move is the mechanic, not a UI convention.
 */

import type { CioView, Plane } from "./cioView";

export interface Session {
  session_id: string;
  run_id: string;
  world_id: string;
  months: number;
  revealed_months: number;
  basis: "reported" | "actual";
  ranked: boolean;
  participant: string | null;
  decisions: Record<string, string>;
  window_log: unknown[];
  status: "active" | "completed";
  decision_windows?: number[];
  /** the book's value at the reveal pointer; null before the tape opens */
  value?: number | null;
  /** the hold-course twin's value at the same point — the bar to clear */
  twin_value?: number | null;
  /** cash on hand at the reveal pointer */
  cash?: number | null;
  /** unfunded commitments over TRUE assets — the honest denominator */
  coverage_true?: number | null;
  /** the same ratio on appraisal-smoothed marks — reads healthiest when it isn't */
  coverage_reported?: number | null;
  /** the private sleeve's true weight of the book, for the policy-band check */
  private_weight_true?: number | null;
  calls_paid?: number | null;
  distributions_received?: number | null;
  spending_paid?: number | null;
  /** sum of every forced sale this quarter, across cause and kind */
  forced_sale_total?: number | null;
  /** ER-6's visible lapse (audit F2): undrawn commitment CANCELLED at the end
   * of a fund's contractual life — released, never called. It fires in one
   * quarter of a decade, so the running total is what keeps it on the page. */
  expired_undrawn?: number | null;
  expired_undrawn_to_date?: number | null;
  /** sp-02 (E1): the plan's next per-sleeve commitment points, SERVER-computed
   * at the pointer — the lever's pre-fill; committing these IS holding to plan */
  next_plan_commitments?: Record<string, number> | null;
  /** audit F4: the state the pre-fill was computed from — the last CLOSED
   * quarter. The engine paces on the weight at the commitment quarter, whose
   * returns are unrevealed here, so the pre-fill is declared rather than
   * silently approximate. An untouched sleeve is paced fresh server-side. */
  next_plan_basis?: {
    as_of_quarter: number;
    as_of_month: number;
    private_weight_reported: number;
  } | null;
  /** su-app-06 section 4.3: on a session carrying an entered CommitmentPlan,
   * what the POLICY pacing rule would have paced at the current reported
   * weight. Shown beside the plan number as a comparison, never applied —
   * `next_plan_commitments` is the plan, and an untouched lever commits it.
   * Null for a session with no stored plan, where the pacing rule IS the
   * pre-fill and there is nothing to compare it against. */
  plan_pace?: Record<string, number> | null;
  /** audit F4: what the spending rate was applied to, and the rate — so
   * `spending_paid` is rederivable from this document alone. Quarter-end
   * `nav_reported` is sampled after the waterfall and does NOT reproduce it. */
  spending_basis?: number | null;
  spending_rate_annual?: number | null;
  /** the weight the COMMITTEE sees, which is what the pacing rule reads */
  private_weight_reported?: number | null;
  /** sp-05 (E1): the ladder by vintage at the pointer, and the trailing
   * distribution series — visible at the moment of decision */
  vintage_nav?: Record<string, number> | null;
  trailing_distributions?: number[] | null;
  forced_sales?: {
    period: number;
    amount: number;
    cause: string;
    kind: string;
    sleeves_sold: string[];
    /** forced-secondary entries only */
    nav_sold?: number;
    /** forced-secondary entries only */
    haircut?: number;
  }[];
}

export interface OutcomeWindow {
  month: number;
  action: string;
  contribution: number;
}

export interface Outcome {
  session_id: string;
  basis: string;
  ranked: boolean;
  decision_alpha_version: string;
  final_value: number;
  twin_final_value: number;
  alpha: number;
  windows: OutcomeWindow[];
  /** E7: three series by contract; drift_twin is null until its engine work lands. */
  series?: { active: number[]; twin: number[]; drift_twin: number[] | null };
  /** per-window chain-link contribution, in window order; sums exactly to `alpha`. */
  window_contributions: number[];
  /** count of forced-secondary sales over the whole run. */
  forced_secondaries: number;
  /** sp-03 (E4): the flinch cost and the arithmetic warning — server-authored
   * lines, the number stated without smugness. */
  annotations?: {
    type: string;
    month: number;
    text: string;
    distribution_shortfall?: number;
    cost?: number;
  }[];
}

export type Action = "hold" | "derisk" | "leanin" | "secondary";

export const ACTIONS: readonly Action[] = ["hold", "derisk", "leanin", "secondary"];

export class SessionApiError extends Error {
  constructor(
    public readonly status: number,
    detail: string,
  ) {
    super(detail);
  }
}

/**
 * FastAPI's `detail` has two shapes and only one of them is a string.
 *
 * Our own `HTTPException(422, detail="book totals 103, must total 100")`
 * gives a string. A pydantic-level failure — a rung field that will not
 * parse, an unknown key under `extra="forbid"` — gives a LIST of
 * `{loc, msg, type}` objects, which `String(...)` renders as
 * `[object Object]`. That is what the book entry screen showed for roughly
 * half of the refusals it can provoke, which is the same as showing nothing.
 *
 * Exported as a pure seam so the rendering is pinned without a live server.
 */
export function renderDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail !== "") return detail;
  if (Array.isArray(detail)) {
    const lines = detail
      .map((entry) => {
        if (typeof entry === "string") return entry;
        if (entry && typeof entry === "object") {
          const item = entry as { loc?: unknown; msg?: unknown };
          const where = Array.isArray(item.loc) ? item.loc.join(".") : "";
          const msg = typeof item.msg === "string" ? item.msg : JSON.stringify(entry);
          return where ? `${where}: ${msg}` : msg;
        }
        return String(entry);
      })
      .filter((line) => line !== "");
    if (lines.length) return lines.join("; ");
  } else if (detail && typeof detail === "object") {
    return JSON.stringify(detail);
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = renderDetail((await res.json()).detail, detail);
    } catch {
      /* non-JSON error body; statusText stands */
    }
    throw new SessionApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

/** su-app-06: a ten-rung private-sleeve cohort, as served/entered. Shape
 * only — `identity`/`commitment`/`value` carry whatever the server put
 * there; this client edits seven named fields and passes the rest through
 * untouched (`recallable_balance`, `cumulative_recycled` included). */
export interface Rung {
  identity: { vintage_year: number; [k: string]: unknown };
  commitment: {
    committed: number;
    paid_in: number;
    unfunded: number;
    recallable_balance: number;
    cumulative_recycled: number;
  };
  value: { nav_true: number; nav_reported: number; cumulative_distributions: number };
  [k: string]: unknown;
}

/** su-app-06: the opening book contract (`opening-book-0.1`). `liquid`'s
 * key set is engine-dependent — never hardcode it, read `liquid_sleeves`
 * off `DefaultBookResponse` instead. */
export interface Book {
  state_version: string;
  liquid: Record<string, number>;
  private: Record<string, Rung[]>;
  cash: number;
}

/** su-app-06: the commitment plan contract (`commitment-plan-0.1`). Each
 * `points[sleeve]` array has one entry per decision window (nine, not ten
 * years) — driven by the served array's length, never a constant. */
export interface Plan {
  state_version: string;
  points: Record<string, number[]>;
}

export interface DefaultBookResponse {
  book: Book;
  plan: Plan;
  liquid_sleeves: string[];
  book_digest: string;
  plan_digest: string;
}

/** su-app-06: the entry screen's pre-fill — today's derived book and the
 * flat fixed-rule plan, for this world's own sleeve set. */
export function getDefaultBook(runId: string): Promise<DefaultBookResponse> {
  return request(`/book/default?run_id=${encodeURIComponent(runId)}`);
}

export function createSession(body: {
  run_id: string;
  basis?: "reported" | "actual";
  ranked?: boolean;
  participant?: string;
  book?: Book;
  plan?: Plan;
}): Promise<Session> {
  return request("/sessions", { method: "POST", body: JSON.stringify(body) });
}

export function getSession(sid: string): Promise<Session> {
  return request(`/sessions/${sid}`);
}

export function advance(sid: string, toMonth: number): Promise<Session> {
  return request(`/sessions/${sid}/advance`, {
    method: "POST",
    body: JSON.stringify({ to_month: toMonth }),
  });
}

/** DN-6 §8 client telemetry riding along with a decision (never scored). */
export interface ClientLog {
  time_on_window_ms?: number;
  basis_toggles?: number;
  ui_version?: string;
}

export function decide(
  sid: string,
  month: number,
  action: Action,
  clientLog: ClientLog = {},
  commitments: Record<string, number> | null = null,
): Promise<Session> {
  return request(`/sessions/${sid}/decisions`, {
    method: "POST",
    body: JSON.stringify({
      month,
      action,
      client_log: clientLog,
      ...(commitments !== null ? { commitments } : {}),
    }),
  });
}

export function complete(sid: string): Promise<Session> {
  return request(`/sessions/${sid}/complete`, { method: "POST" });
}

export function getOutcome(sid: string): Promise<Outcome> {
  return request(`/sessions/${sid}/outcome`);
}

export interface LeaderboardRow {
  participant: string;
  score: number;
  created_at: string;
}

export interface Board {
  world_id: string;
  seed: number;
  decision_alpha_version: string;
  rows: LeaderboardRow[];
}

/** The triple key is required — boards never mix worlds, seeds, or scoring versions. */
export function getLeaderboard(
  worldId: string,
  seed: number,
  alphaVersion: string,
): Promise<Board> {
  const params = new URLSearchParams({
    seed: String(seed),
    alpha_version: alphaVersion,
  });
  return request(`/leaderboard/${worldId}?${params}`);
}

/** cio-02: the CIO dashboard's payload. Plane change is a REFETCH —
 * the client never transforms planes (DN-8 §2). 409 before the first
 * closed quarter surfaces as SessionApiError(409). */
export function getCioView(
  sid: string,
  plane: Plane,
  forecastQuarters?: number,
): Promise<CioView> {
  const params = new URLSearchParams({ plane });
  if (forecastQuarters !== undefined) {
    params.set("forecast_quarters", String(forecastQuarters));
  }
  return request(`/sessions/${sid}/cio?${params}`);
}
