/**
 * Play mode (su-app-02): the decade with consequences.
 *
 * The server's session is the authority (W5): this component advances the
 * server's pointer year by year, STOPS at each decision window (the server
 * enforces the stop — advancing past an undecided window is a 409, and the
 * UI treats that as the mechanic, not an error), collects a committed
 * decision (E1), and completes into the outcome view.
 *
 * The local slider becomes a viewport within the server's revealed span:
 * you can look back at revealed history freely, but the frontier only moves
 * through the server.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { DecisionWindow } from "./components/DecisionWindow";
import { cumulativeGrowth, FanChart } from "./components/FanChart";
import { Feed } from "./components/Feed";
import { Leaderboard } from "./components/Leaderboard";
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

const HEADLINE_ASSETS = ["equity", "bonds", "pe"] as const;

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

  const step = useCallback(async () => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      // advance to the next window stop, or the horizon once all are decided
      const target =
        nextWindow !== null
          ? Math.min(nextWindow + 1, months)
          : months;
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
  }, [session, nextWindow, months]);

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

  return (
    <main className="shell">
      <header>
        <h1>{bundle.meta.title ?? bundle.meta.world_id}</h1>
        <p className="provenance">
          playing · month {revealed}/{months} · basis {session.basis} ·{" "}
          {windows.filter((m) => String(m) in session.decisions).length}/
          {windows.length} windows decided
        </p>
      </header>

      {atWindow !== null ? (
        <DecisionWindow
          month={atWindow}
          year={Math.floor((atWindow + 1) / 12)}
          onCommit={commit}
          busy={busy}
        />
      ) : (
        <section className="time-control">
          <button onClick={step} disabled={busy}>
            {nextWindow !== null
              ? `Play to year ${Math.floor((nextWindow + 1) / 12)}`
              : "Play out the decade"}
          </button>
        </section>
      )}
      {error && <p className="error">{error}</p>}

      {HEADLINE_ASSETS.map((asset) => (
        <FanChart
          key={asset}
          label={asset}
          bands={bundle.bands[asset]}
          revealed={cumulativeGrowth(column(asset))}
          revealedMonths={revealed}
        />
      ))}

      <Feed artifacts={bundle.feed.artifacts ?? []} revealedMonths={revealed} />
    </main>
  );
}
