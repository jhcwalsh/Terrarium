/**
 * The book entry screen (su-app-06): the analyst's real opening book,
 * entered before the decade starts.
 *
 * Opens pre-filled with the server's derived default (`GET /book/default`)
 * for THIS world's own sleeve set — never blank, and never a hardcoded
 * sleeve list or a hardcoded plan length (`liquid_sleeves` and the served
 * plan's array length drive both). Editing is shape validation only: the
 * running total (`sum(liquid) + sum(rung nav_true) + cash`) is the one
 * piece of arithmetic this screen performs. Everything that scores — NAV,
 * coverage, alpha — comes from the server (DN-3 W5); this screen computes
 * none of it.
 *
 * Ranked eligibility is a SERVER-enforced rule; the note here only states
 * the current position (book+plan still exactly the served default) so the
 * player isn't surprised at `POST /sessions`.
 */

import { useEffect, useMemo, useState } from "react";
import {
  getDefaultBook,
  type Book,
  type DefaultBookResponse,
  type Plan,
  type Rung,
} from "./lib/session";

const RUNG_FIELDS = [
  "vintage_year",
  "committed",
  "paid_in",
  "unfunded",
  "nav_true",
  "nav_reported",
  "cumulative_distributions",
] as const;
type RungField = (typeof RUNG_FIELDS)[number];

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function rungField(rung: Rung, field: RungField): number {
  if (field === "vintage_year") return rung.identity.vintage_year;
  if (field === "committed" || field === "paid_in" || field === "unfunded") {
    return rung.commitment[field];
  }
  return rung.value[field];
}

function withRungField(rung: Rung, field: RungField, value: number): Rung {
  if (field === "vintage_year") {
    return { ...rung, identity: { ...rung.identity, vintage_year: value } };
  }
  if (field === "committed" || field === "paid_in" || field === "unfunded") {
    return { ...rung, commitment: { ...rung.commitment, [field]: value } };
  }
  return { ...rung, value: { ...rung.value, [field]: value } };
}

/** the one piece of arithmetic this screen does — everything else that
 * matters is server-computed. */
function bookTotal(book: Book): number {
  const liquidSum = Object.values(book.liquid).reduce((a, b) => a + b, 0);
  const privateSum = Object.values(book.private)
    .flat()
    .reduce((a, r) => a + r.value.nav_true, 0);
  return liquidSum + privateSum + book.cash;
}

/** every editable field parses to a finite number — the shape check the
 * continue button gates on, independent of what the total happens to be. */
function allFieldsFinite(book: Book, plan: Plan): boolean {
  const liquidOk = Object.values(book.liquid).every(Number.isFinite);
  const cashOk = Number.isFinite(book.cash);
  const rungsOk = Object.values(book.private)
    .flat()
    .every((r) => RUNG_FIELDS.every((f) => Number.isFinite(rungField(r, f))));
  const planOk = Object.values(plan.points).every((arr) => arr.every(Number.isFinite));
  return liquidOk && cashOk && rungsOk && planOk;
}

/** spec section 7's first refusal: "negative anything". A SHAPE check — it
 * compares numbers the analyst typed against zero and computes no value, no
 * NAV and no coverage (DN-3 W5 leaves all of those on the server). */
function allFieldsNonNegative(book: Book, plan: Plan): boolean {
  const ok = (n: number) => n >= 0;
  return (
    Object.values(book.liquid).every(ok) &&
    ok(book.cash) &&
    Object.values(book.private)
      .flat()
      .every((r) => RUNG_FIELDS.every((f) => ok(rungField(r, f)))) &&
    Object.values(plan.points).every((arr) => arr.every(ok))
  );
}

/** `validate_book`'s ``RUNG_TOLERANCE`` — the SERVER's own tolerance, so a
 * book this screen offers cannot be one the server then refuses on the
 * identity, and one it blocks cannot be one the server would have taken. */
const RUNG_TOLERANCE = 1e-9;

/** spec section 7: `paid_in + unfunded = committed + cumulative_recycled`.
 * Deliberately NOT the simpler `paid_in + unfunded = committed`, which
 * recycling legitimately breaks — the same note `ah/port/book.py` carries. */
function recyclingIdentityHolds(book: Book): boolean {
  return Object.values(book.private)
    .flat()
    .every((r) => {
      const lhs = r.commitment.paid_in + r.commitment.unfunded;
      const rhs = r.commitment.committed + r.commitment.cumulative_recycled;
      return Math.abs(lhs - rhs) <= RUNG_TOLERANCE;
    });
}

export function BookEntry({
  runId,
  initialBook,
  initialPlan,
  onReady,
  onCancel,
}: {
  runId: string;
  /** su-app-06 (I3): what the analyst entered last time this screen was
   * open. `POST /sessions` happens two screens later, so a 422 there used to
   * throw away up to 210 typed fields — the screen re-seeded from the server
   * default on the way back in. Seeding from these instead makes a refusal
   * recoverable. Undefined on the first visit. The server's own default is
   * still fetched regardless: it is what `isDefault` and the per-sleeve
   * resets compare against, and it must stay the server's number. */
  initialBook?: Book;
  initialPlan?: Plan;
  onReady: (book: Book, plan: Plan, isDefault: boolean) => void;
  onCancel: () => void;
}) {
  const [resp, setResp] = useState<DefaultBookResponse | null>(null);
  const [book, setBook] = useState<Book | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDefaultBook(runId)
      .then((r) => {
        if (cancelled) return;
        setResp(r);
        setBook(deepClone(initialBook ?? r.book));
        setPlan(deepClone(initialPlan ?? r.plan));
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [runId, initialBook, initialPlan]);

  const isDefault = useMemo(() => {
    if (!resp || !book || !plan) return true;
    return (
      JSON.stringify(book) === JSON.stringify(resp.book) &&
      JSON.stringify(plan) === JSON.stringify(resp.plan)
    );
  }, [resp, book, plan]);

  const total = book ? bookTotal(book) : NaN;
  const totalRounded = Number.isFinite(total) ? Math.round(total * 100) / 100 : NaN;
  // Each refusal the SERVER can raise on shape gets its own named check, so
  // the panel can say which one is blocking rather than only that something
  // is (spec section 6's validity panel).
  // A blank field makes every OTHER rule false as well (NaN fails each
  // comparison), so it is reported alone rather than alongside three
  // consequences of itself.
  const shapeFaults: string[] = [];
  if (book && plan) {
    if (!allFieldsFinite(book, plan)) {
      shapeFaults.push("a field is blank or not a number");
    } else {
      if (!allFieldsNonNegative(book, plan)) shapeFaults.push("a field is negative");
      if (!recyclingIdentityHolds(book)) {
        shapeFaults.push("a rung breaks paid_in + unfunded = committed + recycled");
      }
      if (Math.abs(total - 100) > 0.01) shapeFaults.push("the book does not total 100");
    }
  }
  const ready = !!book && !!plan && shapeFaults.length === 0;

  if (error) {
    return (
      <main className="shell book-entry">
        <p className="error">{error}</p>
        <button onClick={onCancel}>back</button>
      </main>
    );
  }

  if (!resp || !book || !plan) {
    return (
      <main className="shell book-entry">
        <p>Loading the book…</p>
      </main>
    );
  }

  const privateSleeves = Object.keys(resp.book.private);

  const setLiquid = (sleeve: string, value: number) =>
    setBook((b) => (b ? { ...b, liquid: { ...b.liquid, [sleeve]: value } } : b));

  const setCash = (value: number) => setBook((b) => (b ? { ...b, cash: value } : b));

  const setRung = (sleeve: string, i: number, field: RungField, value: number) =>
    setBook((b) => {
      if (!b) return b;
      const rungs = b.private[sleeve].map((r, idx) =>
        idx === i ? withRungField(r, field, value) : r,
      );
      return { ...b, private: { ...b.private, [sleeve]: rungs } };
    });

  const resetSleeve = (sleeve: string) =>
    setBook((b) =>
      b
        ? { ...b, private: { ...b.private, [sleeve]: deepClone(resp.book.private[sleeve]) } }
        : b,
    );

  const setPlanPoint = (sleeve: string, i: number, value: number) =>
    setPlan((p) => {
      if (!p) return p;
      const points = p.points[sleeve].map((v, idx) => (idx === i ? value : v));
      return { ...p, points: { ...p.points, [sleeve]: points } };
    });

  const resetPlan = () => setPlan(deepClone(resp.plan));

  const planYears = plan.points[privateSleeves[0]] ?? [];

  return (
    <main className="shell book-entry">
      <h1>Enter the opening book</h1>
      <p className="tagline">
        Pre-filled with today&apos;s derived book. Edit only what your institution
        actually holds — everything else stays on the plan.
      </p>

      <section className="setup book-liquid">
        <h2>Liquid sleeves</h2>
        {resp.liquid_sleeves.map((sleeve) => (
          <label key={sleeve} className="setup-row">
            <span>{sleeve}</span>
            <input
              type="number"
              aria-label={sleeve}
              value={Number.isFinite(book.liquid[sleeve]) ? book.liquid[sleeve] : ""}
              onChange={(e) => setLiquid(sleeve, Number(e.target.value))}
            />
          </label>
        ))}
        <label className="setup-row">
          <span>cash</span>
          <input
            type="number"
            aria-label="cash"
            value={Number.isFinite(book.cash) ? book.cash : ""}
            onChange={(e) => setCash(Number(e.target.value))}
          />
        </label>
      </section>

      {privateSleeves.map((sleeve) => (
        <section key={sleeve} className="book-ladder">
          <div className="book-ladder-head">
            <h2>{sleeve}</h2>
            <button type="button" onClick={() => resetSleeve(sleeve)}>
              {`Reset ${sleeve}`}
            </button>
          </div>
          <div className="book-ladder-scroll">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  {RUNG_FIELDS.map((f) => (
                    <th key={f}>{f}</th>
                  ))}
                  <th>recallable</th>
                  <th>recycled</th>
                </tr>
              </thead>
              <tbody>
                {book.private[sleeve].map((rung, i) => (
                  <tr key={i}>
                    <td>{i}</td>
                    {RUNG_FIELDS.map((field) => {
                      const v = rungField(rung, field);
                      return (
                        <td key={field}>
                          <input
                            type="number"
                            aria-label={`${sleeve} rung ${i} ${field}`}
                            value={Number.isFinite(v) ? v : ""}
                            onChange={(e) => setRung(sleeve, i, field, Number(e.target.value))}
                          />
                        </td>
                      );
                    })}
                    <td className="book-carry">{rung.commitment.recallable_balance}</td>
                    <td className="book-carry">{rung.commitment.cumulative_recycled}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <section className="book-plan">
        <div className="book-ladder-head">
          <h2>Commitment plan</h2>
          <button type="button" onClick={resetPlan}>
            Reset plan
          </button>
        </div>
        <div className="book-ladder-scroll">
          <table>
            <thead>
              <tr>
                <th>year</th>
                {privateSleeves.map((s) => (
                  <th key={s}>{s}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {planYears.map((_, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  {privateSleeves.map((s) => {
                    const v = plan.points[s]?.[i];
                    return (
                      <td key={s}>
                        <input
                          type="number"
                          aria-label={`${s} plan year ${i}`}
                          value={v !== undefined && Number.isFinite(v) ? v : ""}
                          onChange={(e) => setPlanPoint(s, i, Number(e.target.value))}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="book-rail">
        <div>
          <span className="k">Total</span>
          <span className="v" data-testid="book-total">
            {Number.isFinite(totalRounded) ? totalRounded : "—"}
          </span>
        </div>
      </div>

      {shapeFaults.length > 0 && (
        <p className="book-note error" data-testid="shape-faults">
          {shapeFaults.join("; ")}
        </p>
      )}

      <p className="book-note" data-testid="ranked-note">
        {isDefault
          ? "Ranked is available — this is the default book."
          : "Practice only — you have edited the book."}
      </p>

      <button disabled={!ready} onClick={() => onReady(book, plan, isDefault)}>
        Continue
      </button>
      <button onClick={onCancel}>back</button>
    </main>
  );
}
