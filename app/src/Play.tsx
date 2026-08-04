/**
 * Play mode (su-app-02, vitrine remodel): the decade with consequences.
 *
 * The server's session is the authority (W5): this component advances the
 * server's pointer, STOPS at each decision window (the server enforces the
 * stop — advancing past an undecided window is a 409, and the UI treats
 * that as the mechanic, not an error), collects a committed decision (E1),
 * and completes into the outcome view.
 *
 * Layout is the vitrine: header with clock + transport + plane switch,
 * wire ticker, stat rail, then charts left / allocation + wire + decision
 * right. The plane switch flips the PRIVATE assets' revealed lines
 * between appraisal-smoothed marks (as reported, brass) and true returns
 * (as true, jade) — display only; the scoring basis is fixed at session
 * creation and shown in the rail.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Allocation } from "./components/Allocation";
import { DecisionWindow } from "./components/DecisionWindow";
import { cumulativeGrowth, FanChart } from "./components/FanChart";
import { Feed } from "./components/Feed";
import { Leaderboard } from "./components/Leaderboard";
import { Ticker } from "./components/Ticker";
import { Reckoning } from "./Reckoning";
import type { PlayConfig } from "./RankedSetup";
import type { WorldBundle } from "./lib/bundle";
import {
  advance,
  complete,
  createSession,
  decide,
  getOutcome,
  SessionApiError,
  type Action,
  type Outcome,
  type Session,
} from "./lib/session";

// Display order + names for every asset the bundle carries bands for.
// The engine's contract order, not the JSON's alphabetical key order.
export const ASSET_LABELS: ReadonlyArray<readonly [string, string]> = [
  ["equity", "Equities"],
  ["bonds", "Bonds"],
  ["hy", "High yield"],
  ["commodities", "Commodities"],
  ["reits", "REITs"],
  ["pe", "Private equity"],
  ["pc", "Private credit"],
  ["re", "Real estate"],
];

const PRIVATE_ASSETS = new Set(["pe", "pc", "re"]);

type Plane = "reported" | "true";

interface PlayProps {
  bundle: WorldBundle;
  config?: PlayConfig;
  onExit: () => void;
}

export function Play({ bundle, config, onExit }: PlayProps) {
  const basis = config?.basis ?? "reported";
  const [session, setSession] = useState<Session | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [plane, setPlane] = useState<Plane>("reported");

  const months = bundle.meta.months;
  const windows = bundle.summary.decision_months;

  useEffect(() => {
    createSession({
      run_id: bundle.meta.run_id,
      basis,
      ranked: config?.ranked ?? false,
      participant: config?.participant,
    })
      .then(setSession)
      .catch((e) => setError(String(e)));
  }, [bundle.meta.run_id, basis, config?.ranked, config?.participant]);

  /** The next undecided window, or null when all are decided. */
  const nextWindow = useMemo(() => {
    if (!session) return null;
    return windows.find((m) => !(String(m) in session.decisions)) ?? null;
  }, [session, windows]);

  /** The window the pointer is currently stopped at, if any. */
  const atWindow =
    session && nextWindow !== null && session.revealed_months === nextWindow + 1
      ? nextWindow
      : null;

  const advanceTo = useCallback(
    async (target: number) => {
      if (!session) return;
      setBusy(true);
      setError(null);
      try {
        const updated = await advance(session.session_id, target);
        setSession(updated);
        if (updated.revealed_months >= months) {
          const done = await complete(updated.session_id);
          setSession(done);
          setOutcome(await getOutcome(done.session_id));
        }
      } catch (e) {
        setError(e instanceof SessionApiError ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [session, months],
  );

  /** Jump to the next window stop, or the horizon once all are decided. */
  const playAhead = useCallback(() => {
    void advanceTo(nextWindow !== null ? Math.min(nextWindow + 1, months) : months);
  }, [advanceTo, nextWindow, months]);

  /**
   * A quarter at a time — the play rhythm (owner: "let's change the play to
   * quarterly, not annual"). Clamped to the next undecided window because the
   * server refuses to reveal past one (409) and windows sit at month 11, 23,
   * ... — a naive +3 from month 9 would jump the stop.
   *
   * DECISIONS stay annual. Moving them to quarterly would redefine
   * decision_alpha, the DN-5 chain-link decomposition and leaderboard
   * comparability; that needs a decision_alpha_version bump and its own WP.
   */
  const stepQuarter = useCallback(() => {
    if (!session) return;
    const target = session.revealed_months + 3;
    const stop = nextWindow !== null ? nextWindow + 1 : months;
    void advanceTo(Math.min(target, stop, months));
  }, [advanceTo, session, nextWindow, months]);

  const commit = useCallback(
    async (action: Action, timeOnWindowMs: number) => {
      if (!session || atWindow === null) return;
      setBusy(true);
      setError(null);
      try {
        const updated = await decide(session.session_id, atWindow, action, {
          time_on_window_ms: timeOnWindowMs,
          ui_version: "su-app-02",
        });
        setSession(updated);
      } catch (e) {
        setError(e instanceof SessionApiError ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [session, atWindow],
  );

  if (error && !session) {
    return (
      <main className="shell">
        <p className="error">{error}</p>
        <p>
          Play mode needs the session service (`uv run uvicorn ah.serve:app`).
          <button onClick={onExit}>back to browse</button>
        </p>
      </main>
    );
  }
  if (!session) return <main className="shell">opening session…</main>;

  const revealed = session.revealed_months;
  const order = bundle.revealed.series_order;
  const column = (name: string) =>
    bundle.revealed.tape.map((row) => row[order.indexOf(name)]);

  if (outcome) {
    return (
      <Reckoning
        outcome={outcome}
        onExit={onExit}
        board={
          session?.ranked ? (
            <Leaderboard
              worldId={bundle.meta.world_id}
              seed={bundle.meta.seed}
              alphaVersion={outcome.decision_alpha_version}
              highlight={session.participant ?? undefined}
            />
          ) : undefined
        }
      />
    );
  }

  const decided = windows.filter((m) => String(m) in session.decisions).length;
  const yearNow = revealed === 0 ? 1 : Math.floor((revealed - 1) / 12) + 1;
  // the play rhythm is quarterly, so the clock reads in quarters
  const quarterNow = revealed === 0 ? 0 : Math.floor(((revealed - 1) % 12) / 3) + 1;
  const dateNow = revealed === 0 ? "T0" : `Y${yearNow} Q${quarterNow}`;
  const monthNow =
    revealed === 0 ? "before the tape opens" : `month ${((revealed - 1) % 12) + 1} of the year`;
  const nextYear = nextWindow !== null ? Math.floor((nextWindow + 1) / 12) : null;
  const transportLocked = busy || atWindow !== null || revealed >= months;

  return (
    <main className={`vitrine plane-${plane}`}>
      <header className="topbar">
        <div>
          <div className="brand">Terrarium</div>
          <div className="worldname disp">{bundle.meta.title ?? bundle.meta.world_id}</div>
        </div>
        <div className="meta">
          <span className={`chip${session.ranked ? " ranked" : ""}`}>
            {session.ranked ? "Ranked" : "Practice"}
          </span>
          <span className="chip">seed {bundle.meta.seed}</span>
          <span className="chip">scored on {session.basis}</span>
        </div>

        <div className="spacer" />

        <div className="clock">
          <div>
            <div className="yr">
              YEAR {yearNow} OF {Math.ceil(months / 12)}
            </div>
            <div className="date">{dateNow}</div>
          </div>
          <div className="transport">
            <button
              className="t"
              onClick={stepQuarter}
              disabled={transportLocked}
              title="Advance one quarter"
              aria-label="Advance one quarter"
            >
              »
            </button>
            <button
              className="t"
              onClick={playAhead}
              disabled={transportLocked}
              title={nextYear !== null ? `Play to year ${nextYear}` : "Play out the decade"}
              aria-label="Play to the next stop"
            >
              ▶
            </button>
          </div>
        </div>

        <div
          className="switch"
          role="switch"
          aria-checked={plane === "true"}
          tabIndex={0}
          aria-label="Show private assets as reported or as true"
          onClick={() => setPlane(plane === "true" ? "reported" : "true")}
          onKeyDown={(e) => {
            if (e.key === " " || e.key === "Enter") {
              e.preventDefault();
              setPlane(plane === "true" ? "reported" : "true");
            }
          }}
        >
          <div className="knob" />
          <span>As reported</span>
          <span>As true</span>
        </div>

        <button className="t" onClick={onExit} title="Exit to browse" aria-label="Exit">
          ✕
        </button>
      </header>

      <Ticker artifacts={bundle.feed.artifacts ?? []} revealedMonths={revealed} />

      <div className="rail">
        <div className="stat">
          <div className="k">Revealed</div>
          <div className="v">{revealed}</div>
          <div className="s">of {months} months &middot; {monthNow}</div>
        </div>
        <div className="stat">
          <div className="k">Windows decided</div>
          <div className="v">
            {decided}/{windows.length}
          </div>
          <div className="s">
            {nextYear !== null
              ? `annual windows — next stops at year ${nextYear}`
              : "all decided — play it out"}
          </div>
        </div>
        <div className="stat">
          <div className="k">View basis</div>
          <div className="v planeval">{plane === "reported" ? "REPORTED" : "TRUE"}</div>
          <div className="s">
            private marks {plane === "reported" ? "appraised" : "de-smoothed"}
          </div>
        </div>
        <div className="stat">
          <div className="k">Lineage</div>
          <div className={`v ${bundle.meta.digest_verified ? "pos" : "neg"}`}>
            {bundle.meta.digest_verified ? "OK" : "FAIL"}
          </div>
          <div className="s">digest recomputed at build</div>
        </div>
      </div>

      {error && (
        <section>
          <p className="error">{error}</p>
        </section>
      )}

      <div className="vgrid">
        <div className="left">
          <section>
            <div className="eyebrow">
              <span>The market against its siblings</span>
              <span>
                {revealed} of {months} months revealed
              </span>
            </div>
            <div className="chart-grid">
              {ASSET_LABELS.filter(([key]) => bundle.bands[key]).map(([key, name]) => {
                const isPrivate = PRIVATE_ASSETS.has(key);
                const source =
                  isPrivate && plane === "reported" ? `${key}_reported` : key;
                return (
                  <FanChart
                    key={key}
                    label={name}
                    className={isPrivate ? "private" : undefined}
                    bands={bundle.bands[key]}
                    revealed={cumulativeGrowth(column(source))}
                    revealedMonths={revealed}
                  />
                );
              })}
              <p className="fan-key">
                <span className="key-swatch key-revealed" /> this world, as
                revealed
                <br />
                <span className="key-swatch key-inner" /> middle half of{" "}
                {bundle.meta.n_paths} sibling runs
                <br />
                <span className="key-swatch key-outer" /> 5–95% of siblings
                <br />
                <span className="key-swatch key-median" /> median sibling
                <br />
                <br />
                Scale is cumulative return since t0; the figure beside each name
                is the annualized return to date. The hatched region is sealed —
                the future exists but is withheld. Private assets follow the
                reported/true switch, top right.
              </p>
            </div>
          </section>
        </div>

        <div className={`right${atWindow !== null ? " deciding" : ""}`}>
          <section>
            <div className="eyebrow">
              <span>Allocation</span>
              <span>targets, rebalanced at each window</span>
            </div>
            <Allocation decisions={session.decisions} />
          </section>

          <section>
            <div className="eyebrow">
              <span>The wire</span>
              <span>{dateNow}</span>
            </div>
            <Feed artifacts={bundle.feed.artifacts ?? []} revealedMonths={revealed} />
          </section>

          <section className="decision-panel">
            <div className="eyebrow">
              <span>{atWindow !== null ? "Committee in session" : "Actions"}</span>
              <span>{atWindow !== null ? "commit to continue" : `next window · year ${nextYear ?? "—"}`}</span>
            </div>
            <DecisionWindow
              open={atWindow !== null}
              month={atWindow ?? (nextWindow ?? 0)}
              year={Math.floor(((atWindow ?? nextWindow ?? 0) + 1) / 12)}
              nextYear={nextYear}
              onCommit={commit}
              busy={busy}
            />
          </section>
        </div>
      </div>

      <footer>
        <span>SIMULATED WORLD · NOT INVESTMENT ADVICE · NO REAL FIRM OR PERSON APPEARS</span>
        <span>
          RUN {bundle.meta.run_id.slice(0, 8).toUpperCase()} · SEED {bundle.meta.seed} ·
          REPLAYABLE FROM SEED
        </span>
      </footer>
    </main>
  );
}
