/**
 * Session-service client (su-app-02; DN-3 W5).
 *
 * Everything that scores round-trips the server: the reveal pointer during
 * play, decisions, completion, the outcome. This module is a thin, typed
 * fetch wrapper over ah.serve — it holds NO game logic, because the server
 * refusing an illegal move is the mechanic, not a UI convention.
 */

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
  /** sp-02 (E1): the plan's next per-sleeve commitment points, SERVER-computed
   * at the pointer — the lever's pre-fill; committing these IS holding to plan */
  next_plan_commitments?: Record<string, number> | null;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body; statusText stands */
    }
    throw new SessionApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export function createSession(body: {
  run_id: string;
  basis?: "reported" | "actual";
  ranked?: boolean;
  participant?: string;
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
