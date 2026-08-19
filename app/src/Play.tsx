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
import { BandRow } from "./components/BandRow";
import CioDashboard, { type ExtraTab } from "./components/CioDashboard";
import { DecisionWindow } from "./components/DecisionWindow";
import { cumulativeGrowth, FanChart } from "./components/FanChart";
import { Feed } from "./components/Feed";
import { Leaderboard } from "./components/Leaderboard";
import Provenance from "./components/Provenance";
import { Ticker } from "./components/Ticker";
import { Reckoning } from "./Reckoning";
import type { PlayConfig } from "./RankedSetup";
import { ASSET_LABELS } from "./lib/assetLabels";
import type { WorldBundle } from "./lib/bundle";
import { type CioView, type Plane, validateCioView } from "./lib/cioView";
import { usd } from "./lib/money";
import {
  advance,
  complete,
  createSession,
  decide,
  getCioView,
  getOutcome,
  planeForBasis,
  SessionApiError,
  type Action,
  type Book,
  type Outcome,
  type Plan,
  type Session,
} from "./lib/session";

// Display order + names for every asset the bundle carries bands for, and
// its display name lookup — moved to lib/assetLabels.ts (app-open-02) so
// components/BandRow.tsx can share it without importing back out of this
// file (Play.tsx already imports DecisionWindow, which now imports
// BandRow). Re-exported here so App.tsx's existing `import { ASSET_LABELS }
// from "./Play"` is unaffected.
export { ASSET_LABELS };

const PRIVATE_ASSETS = new Set(["pe", "pc", "re", "infra"]);

// Plane is re-exported from lib/cioView.ts (cio-02) rather than declared
// here a second time — it is the same "reported" | "true" domain the plane
// switch has always driven, and the CIO dashboard now shares the switch.

/** percentile name -> cumulative growth series, per asset — bundle.bands' shape. */
export type BundleBands = Record<string, Record<string, number[]>>;

/**
 * The peer-cone tab the cockpit injects into the dashboard. Host-owned
 * content: the cone comes from the world bundle, not from CioView, which
 * is why it rides as an injected tab and never moves into the dashboard
 * (DN-8 §1 - the dashboard renders one CioView and nothing else).
 *
 * `seriesFor` is the accessor Play already holds — `column`, built off
 * `bundle.revealed.tape`, called per asset key so private assets resolve
 * through the reported/true plane switch (`${key}_reported` vs `key`)
 * before this factory ever sees them.
 *
 * Deliberately omits book mode's eyebrow and non-stacked `.fan-key`
 * description paragraph — those stay put in `Play`'s book-mode section
 * so this tab doesn't double them. Only the `.chart-grid` (the nine
 * charts plus the stacked legend — ER-14 close-out's fourth private
 * class, infra, joined the other eight) is shared.
 */
export function peerTabs(
  bands: BundleBands | null,
  seriesFor: (assetKey: string) => number[],
  revealedMonths: number,
  plane: Plane = "reported",
  nPaths = 0,
): ExtraTab[] {
  if (!bands) return [];
  return [
    {
      key: "peers",
      label: "Peers",
      render: () => (
        <div className="chart-grid">
          {ASSET_LABELS.filter(([key]) => bands[key]).map(([key, name]) => {
            const isPrivate = PRIVATE_ASSETS.has(key);
            const source = isPrivate && plane === "reported" ? `${key}_reported` : key;
            return (
              <FanChart
                key={key}
                label={name}
                className={isPrivate ? "private" : undefined}
                bands={bands[key]}
                revealed={cumulativeGrowth(seriesFor(source))}
                revealedMonths={revealedMonths}
              />
            );
          })}
          <p className="fan-key stacked">
            <span className="key-swatch key-revealed" /> this world, as
            revealed
            <br />
            <span className="key-swatch key-inner" /> middle half of{" "}
            {nPaths} sibling runs
            <br />
            <span className="key-swatch key-outer" /> 5–95% of siblings
            <br />
            <span className="key-swatch key-median" /> median sibling
          </p>
        </div>
      ),
    },
  ];
}

/**
 * When the CIO view must refetch: the pointer moved, the plane changed, or a
 * decision landed. `decisionCount` is `Object.keys(session.decisions).length`
 * — deciding a window updates the session without moving revealed_months (the
 * pointer only advances on the next `advance()` call), so the pointer+plane
 * key alone goes stale the instant `decide()` resolves while CIO mode is on
 * screen. The server rebuilds the CioView from the session's decisions; the
 * client must refetch whenever that input changed.
 */
export function cioFetchKey(
  sid: string,
  revealedMonths: number,
  plane: Plane,
  decisionCount: number,
): string {
  return `${sid}:${revealedMonths}:${plane}:${decisionCount}`;
}

/** The vitrine's class list. CIO mode is a distinct layout mode, not a
 * swapped panel: the dashboard pane scrolls inside itself so the header,
 * ticker, rail and decision panel stay put (styles.css one-screen rule). */
export function cockpitClass(viewMode: "book" | "cio", plane: Plane): string {
  return `vitrine plane-${plane}${viewMode === "cio" ? " cockpit" : ""}`;
}

/** The stat rail's "Your book" label, naming the FIXED scoring basis the
 * figure below it is computed on (`session.basis`, `serve.py`'s
 * `use_reported`) — never the dashboard's live plane, which can disagree
 * with it the instant a player flips the plane switch (I-4; DN-8 §4 lists
 * `plan.totalValue` as plane-sensitive). Extracted as a pure seam, like
 * `cioFetchKey`/`cockpitClass` above, so the label — and specifically that
 * it reads the real `session.basis` rather than a hardcoded string — is
 * pinned by a test without mounting the session-backed component. */
export function bookLabel(basis: string): string {
  return `Your book · ${basis} basis`;
}

/**
 * su-app-07 task 4b: the policy-band report, rendered.
 *
 * The band a player entered on the entry screen is only a feature if a
 * breach appears somewhere. This is that somewhere: one row per sleeve the
 * server judged, in the SERVER'S order (`serve.py::_band_report` emits the
 * world's own sleeve order — liquid then private — and the renderer does not
 * sort), showing the weight and status on the plane this session's basis
 * names.
 *
 * Three things it deliberately does NOT do:
 *
 *  - it never recomputes `alert`. The server judges on unrounded weights
 *    while serving them rounded to 4dp, so a client re-running the rule
 *    would agree almost always and disagree exactly at a band edge — the
 *    one place the number matters (DN-3 W5; `_band_report`'s docstring says
 *    this explicitly). The served word is printed.
 *  - it never picks the plane by hand. `session.basis` is
 *    `"reported" | "actual"` and the report's planes are
 *    `"reported" | "true"`; `planeForBasis` in lib/session.ts is the one
 *    place that mapping lives, and this is its first runtime consumer.
 *  - it never names a sleeve set. Rows come from the server; a sleeve with
 *    no declared range is simply absent, so there is no "no band" state to
 *    render. `ASSET_LABELS` is consulted only for a display NAME, falling
 *    back to the raw key for anything it does not know.
 *
 * Renders `null` — not an empty frame — when there is no report or no
 * banded sleeve, so a session without ranges looks exactly as it did.
 */
export function BandPanel({ session }: { session: Session }) {
  const rows = session.band_report?.sleeves ?? [];
  if (rows.length === 0) return null;
  const plane = planeForBasis(session.basis);
  return (
    <section className="band-panel">
      <div className="eyebrow">
        <span>Policy bands</span>
        <span>
          {plane} weights &middot; last closed quarter &middot; reporting only
        </span>
      </div>
      <ul className="band-cells">
        {rows.map((row) => (
          <BandRow key={row.sleeve} row={row} plane={plane} />
        ))}
      </ul>
    </section>
  );
}

interface PlayProps {
  bundle: WorldBundle;
  config?: PlayConfig;
  /** su-app-06: the analyst's entered opening book/plan, from BookEntry's
   * onReady. Undefined (bundle picked without going through book entry)
   * falls through to the server's own default — createSession's body just
   * omits the keys, same as before this WP. */
  book?: Book;
  plan?: Plan;
  onExit: () => void;
}

export function Play({ bundle, config, book, plan, onExit }: PlayProps) {
  const basis = config?.basis ?? "reported";
  const [session, setSession] = useState<Session | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [plane, setPlane] = useState<Plane>("reported");
  // app-open-01 item 1 (owner-dictated 2026-08-16): the CIO is the front
  // door. After the opening book is confirmed the first thing a player
  // sees is this dashboard, populated with STARTING values — the timeline
  // (book mode) is reached FROM here via the same modeswitch button that
  // already went the other way (cio-02). The server backs revealed_months
  // === 0 now (cio-05 / ah/cioview.py), so this default no longer hits the
  // "no closed quarter yet" 409 it used to.
  const [viewMode, setViewMode] = useState<"book" | "cio">("cio");
  const [cioView, setCioView] = useState<CioView | null>(null);
  const [cioError, setCioError] = useState<string | null>(null);

  const months = bundle.meta.months;
  const windows = bundle.summary.decision_months;

  useEffect(() => {
    createSession({
      run_id: bundle.meta.run_id,
      basis,
      ranked: config?.ranked ?? false,
      participant: config?.participant,
      book,
      plan,
    })
      .then(setSession)
      // su-app-06 (I3): the server's own refusal text, not "Error: ...".
      // A refused book is the one failure here a player can act on, and
      // `SessionApiError.message` now renders a pydantic-shaped detail
      // readably (lib/session.ts renderDetail).
      .catch((e) => setError(e instanceof SessionApiError ? e.message : String(e)));
  }, [bundle.meta.run_id, basis, config?.ranked, config?.participant, book, plan]);

  // cio-02: fetch the CIO view only while that mode is on screen, and only
  // when the pointer, the plane, or the decided-window count actually moved
  // (cioFetchKey). The client never derives the dashboard's numbers itself —
  // a plane change (or a decision) is a REFETCH of the server's own
  // recomputation, same as everywhere else in this file (DN-8 §2).
  //
  // The key is computed once here (not re-derived separately for the effect
  // deps) so the two cannot drift: whatever cioFetchKey consumes IS what
  // retriggers the fetch. The effect body reads `session`/`plane` fresh off
  // the closure — they are current as of the render that produced this key.
  const cioKey = session
    ? cioFetchKey(
        session.session_id,
        session.revealed_months,
        plane,
        Object.keys(session.decisions).length,
      )
    : null;

  useEffect(() => {
    if (viewMode !== "cio" || !session) return;
    let stale = false;
    setCioError(null);
    getCioView(session.session_id, plane)
      .then((v) => {
        if (stale) return;
        if (import.meta.env.DEV) {
          const errs = validateCioView(v);
          if (errs.length) console.warn("[cioView] contract violations:", errs);
        }
        setCioView(v);
      })
      .catch((e) => {
        if (stale) return;
        if (e instanceof SessionApiError && e.status === 409) {
          setCioView(null);
          setCioError("No closed quarter yet - advance past the first quarter.");
        } else {
          setCioError(String(e.message ?? e));
        }
      });
    return () => {
      stale = true;
    };
    // Deps are [viewMode, cioKey] rather than the individual fields cioKey
    // is built from (session?.session_id, session?.revealed_months, plane,
    // decisionCount) on purpose — cioKey IS those fields, so there is only
    // one signal to keep in sync with what the effect body reads.
  }, [viewMode, cioKey]);

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
    async (
      action: Action,
      timeOnWindowMs: number,
      commitments: Record<string, number> | null = null,
    ) => {
      if (!session || atWindow === null) return;
      setBusy(true);
      setError(null);
      try {
        const updated = await decide(
          session.session_id,
          atWindow,
          action,
          {
            time_on_window_ms: timeOnWindowMs,
            ui_version: "su-app-02",
          },
          commitments,
        );
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
          If the server refused the book, go back and re-open &quot;play this
          world&quot; — the entry screen reopens on what you typed, not on the
          server default.
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
  // cio-03 task 4: the nine peer-cone fan charts live in exactly one place
  // now — this factory call, rendered as book mode's chart section AND as
  // the cockpit's injected Peers tab.
  const peerTab = peerTabs(bundle.bands, column, revealed, plane, bundle.meta.n_paths);

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

  // Forced sales are a liquidity event on the player's OWN book (the twin
  // never forces a sale — it holds course by construction), so they come
  // from the session, not the bundle. Merged into the same feed the bundle
  // ships so Feed/Ticker's existing reveal filter (month < revealedMonths)
  // is the one gate for both — no separate discipline to get wrong here.
  const forcedItems = (session.forced_sales ?? []).map((e) => ({
    month: e.period * 3 - 1,
    type: "forced_sale",
    payload: {
      dateline: `Y${Math.floor((e.period * 3 - 1) / 12) + 1}M${(((e.period * 3 - 1) % 12) + 1)}`,
      headline:
        e.kind === "forced_secondary"
          ? `FORCED SALE: ${e.amount.toFixed(1)} raised at a discount — ${e.cause}`
          : `Holdings sold to cover the shortfall: ${e.amount.toFixed(1)}`,
    },
  }));
  const wire = [...(bundle.feed.artifacts ?? []), ...forcedItems];

  const decided = windows.filter((m) => String(m) in session.decisions).length;
  const yearNow = revealed === 0 ? 1 : Math.floor((revealed - 1) / 12) + 1;
  // the play rhythm is quarterly, so the clock reads in quarters
  const quarterNow = revealed === 0 ? 0 : Math.floor(((revealed - 1) % 12) / 3) + 1;
  const dateNow = revealed === 0 ? "T0" : `Y${yearNow} Q${quarterNow}`;
  const monthNow =
    revealed === 0 ? "before the tape opens" : `month ${((revealed - 1) % 12) + 1} of the year`;
  const nextYear = nextWindow !== null ? Math.floor((nextWindow + 1) / 12) : null;
  // The server marks the book to market at the pointer and sends the twin's
  // value beside it; the difference is decision alpha SO FAR, which is the
  // only number that tells a player whether their choices are working.
  const aheadOfTwin =
    session.value != null && session.twin_value != null
      ? session.value - session.twin_value
      : null;
  const transportLocked = busy || atWindow !== null || revealed >= months;

  return (
    <main className={cockpitClass(viewMode, plane)}>
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

        <button
          className="modeswitch"
          aria-pressed={viewMode === "cio"}
          onClick={() => setViewMode(viewMode === "cio" ? "book" : "cio")}
        >
          {viewMode === "cio" ? "Book view" : "CIO view"}
        </button>

        <button className="t" onClick={onExit} title="Exit to browse" aria-label="Exit">
          ✕
        </button>
      </header>

      <Ticker artifacts={wire} revealedMonths={revealed} />

      <div className="rail">
        <div className="stat">
          {/* session.value is computed server-side on the session's FIXED
              scoring basis (serve.py: use_reported = doc["basis"] ==
              "reported"), while the CIO dashboard's plan.totalValue is
              plane-sensitive (cioview.py::_quarterly_returns keys on
              nav_reported/nav_true; DN-8 s4 lists plan.totalValue as
              plane-sensitive). Deleting Book.tsx did not close the basis
              mismatch the way the plan claimed — it moved to this rail: the
              two value figures sit inches apart the moment a player flips
              the plane away from the session basis. Book.tsx used to carry
              this exact label (f35e64d) for the same reason; restored here
              so the rail's headline is never silently read as the same
              number as the dashboard's plan total (I-4). `bookLabel` is
              pinned in Play.cio.test.tsx. */}
          <div className="k">{bookLabel(session.basis)}</div>
          {/* app-open-01 item 1 (owner ruling 2026-08-16): "YOUR BOOK" is a
              VALUE readout, so it gets the $10bn display denomination
              outright (money.ts usd()) — session.value itself is untouched,
              still the scored points the server returns. */}
          <div className={`v ${aheadOfTwin === null ? "" : aheadOfTwin >= 0 ? "pos" : "neg"}`}>
            {usd(session.value ?? 100)}
          </div>
          <div className="s">
            {aheadOfTwin === null
              ? `started at ${usd(100)} · ${monthNow}`
              : // decision alpha-so-far is the scored truth in points; the
                // dollar figure rides alongside, never in place of it.
                `${aheadOfTwin >= 0 ? "+" : "−"}${Math.abs(aheadOfTwin).toFixed(2)} pts vs hold-course twin · ${usd(aheadOfTwin)}`}
          </div>
        </div>
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

      {/* su-app-07 task 4b: a band strip directly under the rail, in BOTH
          view modes. It is session data, so it stays outside CioDashboard,
          which renders one CioView and nothing else (DN-8 §1). It collapses
          to nothing on a session with no ranges. */}
      <BandPanel session={session} />

      {error && (
        <section>
          <p className="error">{error}</p>
        </section>
      )}

      <div className="vgrid">
        <div className="left">
          {viewMode === "cio" ? (
            <div className="cockpit-pane">
              {cioError ? (
                <div className="empty">{cioError}</div>
              ) : cioView ? (
                <CioDashboard
                  view={cioView}
                  onPlaneChange={setPlane}
                  chrome="embedded"
                  extraTabs={peerTab}
                />
              ) : (
                <div className="empty">Loading the CIO view...</div>
              )}
            </div>
          ) : (
          <section>
            <div className="eyebrow">
              <span>The market against its siblings</span>
              <span>
                {revealed} of {months} months revealed
              </span>
            </div>
            <p className="fan-key">
              <span className="key-swatch key-revealed" /> this world
              {" · "}
              <span className="key-swatch key-inner" /> middle half of{" "}
              {bundle.meta.n_paths} siblings
              {" · "}
              <span className="key-swatch key-outer" /> 5–95%
              {" · "}
              <span className="key-swatch key-median" /> median
              {" · "}
              cumulative return since t0, annualized figure beside each name
              {" · "}
              hatched is sealed
            </p>
            {peerTab[0]?.render()}
          </section>
          )}
        </div>

        <div className={`right${atWindow !== null ? " deciding" : ""}`}>
          <section className="wire-panel">
            <div className="eyebrow">
              <span>The wire</span>
              <span>{dateNow}</span>
            </div>
            <Feed artifacts={wire} revealedMonths={revealed} />
            <Provenance bundle={bundle} />
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
              planCommitments={session?.next_plan_commitments ?? null}
              planBasis={session?.next_plan_basis ?? null}
              planPace={session?.plan_pace ?? null}
              bandReport={session?.band_report ?? null}
              basis={session?.basis}
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
