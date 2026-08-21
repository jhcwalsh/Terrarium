/**
 * su-app-02 acceptance: E1's commitment affordance.
 *
 * The register row's requirement, tested at the surface that implements it:
 * NOTHING commits until the player chooses — hold is an explicit selection
 * with the same weight as acting, never a click-through default.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DecisionWindow } from "./DecisionWindow";
import type { AlertLevel } from "../lib/cioView";
import type { BandSleeve } from "../lib/session";

let root: Root | null = null;
let host: HTMLElement | null = null;

function render(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root!.render(ui));
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
});

describe("DecisionWindow (E1)", () => {
  it("commit is disabled until an action is explicitly chosen — hold included", () => {
    const onCommit = vi.fn();
    render(<DecisionWindow open month={11} onCommit={onCommit} />);
    const commit = host!.querySelector<HTMLButtonElement>("button.commit")!;
    expect(commit.disabled).toBe(true);
    act(() => commit.click());
    expect(onCommit).not.toHaveBeenCalled();

    // choosing HOLD is a commitment, not a default
    const hold = host!.querySelector<HTMLInputElement>('input[type="radio"]')!;
    act(() => hold.click());
    expect(commit.disabled).toBe(false);
    act(() => commit.click());
    expect(onCommit).toHaveBeenCalledTimes(1);
    const [action, timeOnWindow] = onCommit.mock.calls[0];
    expect(action).toBe("hold");
    expect(typeof timeOnWindow).toBe("number");
  });

  it("all four actions are on the card", () => {
    render(<DecisionWindow open month={11} onCommit={() => {}} />);
    const labels = [...host!.querySelectorAll(".action-card strong")].map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["Hold course", "De-risk", "Lean in", "Secondary sale"]);
  });

  it("shows each lever's dollar impact next to its points (app-open-01 item 2)", () => {
    // No new data — the fixed 10pt rebalance size the copy already states,
    // rendered through the same usd() as everywhere else in the app.
    render(<DecisionWindow open month={11} onCommit={() => {}} />);
    const badges = [...host!.querySelectorAll(".action-card .k")].map((el) => el.textContent);
    expect(badges[0]).toBe("NO TRADE"); // hold: no rebalance, no dollar figure
    // two-decimal bn precision is app-open-01 review round fix 3
    expect(badges[1]).toBe("10PTS / $1.00bn → BONDS/PC"); // derisk
    expect(badges[2]).toBe("10PTS / $1.00bn → EQ/PE"); // leanin
    expect(badges[3]).toBe("−18% DISCOUNT"); // secondary: a rate, stays a percentage
  });

  it("sends ONLY the sleeves the player touched, so the rest stay exactly on plan", () => {
    /**
     * Audit F4. The pre-fill is the plan as at the last CLOSED quarter, while
     * the engine commits on the weight at the commitment quarter — up to 7.9%
     * apart, and unfixable here because that quarter's returns are unrevealed
     * (computing the pre-fill from them would leak the tape).
     *
     * The old lever merged the whole pre-fill into its state as soon as ONE
     * sleeve was edited, so touching pe silently froze pc and re at stale
     * numbers the player believed were "the plan". Sending only what was
     * touched makes the untouched sleeves fall through to the server's own
     * fresh computation, which is the exact plan.
     */
    const onCommit = vi.fn();
    const plan = { pe: 1.5, pc: 1.2, re: 0.9 };
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={onCommit}
        planCommitments={plan}
        planBasis={{ as_of_quarter: 3, as_of_month: 11, private_weight_reported: 0.31 }}
      />,
    );
    const inputs = [...host!.querySelectorAll<HTMLInputElement>(".lever-row input")];
    // infra carries no entry in this test's plan, so its row falls through
    // to shown()'s zero default — the fourth row (ER-14 close-out).
    expect(inputs.map((i) => i.value)).toEqual(["1.50", "1.20", "0.90", "0.00"]);

    // edit ONE sleeve
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      )!.set!;
      setter.call(inputs[0], "2.00");
      inputs[0].dispatchEvent(new Event("input", { bubbles: true }));
    });

    act(() => host!.querySelector<HTMLInputElement>('input[type="radio"]')!.click());
    act(() => host!.querySelector<HTMLButtonElement>("button.commit")!.click());

    const commitments = onCommit.mock.calls[0][2];
    expect(commitments).toEqual({ pe: 2 });
    expect(commitments).not.toHaveProperty("pc");
    expect(commitments).not.toHaveProperty("re");
    expect(commitments).not.toHaveProperty("infra");
  });

  it("offers a commit row for every private sleeve the server serves, infra included (ER-14 close-out)", () => {
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={() => {}}
        planCommitments={{ pe: 1.5, pc: 1.2, re: 0.9, infra: 0.4 }}
      />,
    );
    const infra = host!.querySelector<HTMLInputElement>('[aria-label="Infrastructure commitment"]');
    expect(infra).not.toBeNull();
    expect(infra!.value).toBe("0.40");
    // and the row is the FOURTH lever row, not a fifth appended elsewhere
    const rows = [...host!.querySelectorAll(".lever-row")];
    expect(rows).toHaveLength(4);
    expect(rows[3].querySelector("input")).toBe(infra);
  });

  it("declares the state the pre-fill was computed from", () => {
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={() => {}}
        planCommitments={{ pe: 1.5, pc: 1.2, re: 0.9 }}
        planBasis={{ as_of_quarter: 3, as_of_month: 11, private_weight_reported: 0.31 }}
      />,
    );
    const note = host!.querySelector(".lever-basis")!.textContent!;
    expect(note).toContain("month 11");
  });

  it("shows the pacing rule's number beside the plan's, labelled and not applied", () => {
    /**
     * su-app-06 sections 4.3 and 6 (C2). The server has served `plan_pace`
     * since task 6 and nothing rendered it, so the pacing flex went from
     * silently APPLIED to silently INVISIBLE. It must appear beside each
     * sleeve's plan figure, labelled as the pacing rule's view.
     *
     * Asserting the label exists is not enough — a render that put the
     * pacing number INTO the input would also produce a label. The input's
     * value is checked here too: what the lever will commit stays the plan.
     */
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={() => {}}
        planCommitments={{ pe: 5, pc: 1.2, re: 0.9 }}
        planPace={{ pe: 3.18, pc: 1.44, re: 1.26 }}
      />,
    );
    const rows = [...host!.querySelectorAll(".lever-row")];
    expect(rows[0].querySelector(".lever-plan")!.textContent).toContain("5.00");
    expect(rows[0].querySelector(".lever-pace")!.textContent).toMatch(/pacing rule\s+3\.18/);
    expect(rows[1].querySelector(".lever-pace")!.textContent).toMatch(/1\.44/);
    // the committed number is the PLAN's, not the pacing rule's
    expect(rows[0].querySelector("input")!.value).toBe("5.00");
  });

  it("explains the plan-carrying session, where the F4 caveat is suppressed", () => {
    /**
     * The server sets `next_plan_basis` to null for plan-carrying sessions
     * (nothing is approximated), which switched OFF the only paragraph the
     * lever had. Those sessions were left with no explanation at all. The
     * plan-carrying explanation replaces it; the F4 caveat still governs
     * sessions without a plan (covered by the test above).
     */
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={() => {}}
        planCommitments={{ pe: 5, pc: 1.2, re: 0.9 }}
        planBasis={null}
        planPace={{ pe: 3.18, pc: 1.44, re: 1.26 }}
      />,
    );
    expect(host!.querySelector(".lever-basis")).toBeNull();
    const note = host!.querySelector(".lever-plan-note")!.textContent!;
    expect(note).toMatch(/leave alone commits exactly what is shown/i);
  });

  it("a session with no plan gets neither the pacing column nor the plan note", () => {
    // the Task 6 scope fence at the surface: no stored plan => no plan_pace,
    // and the F4 caveat is the paragraph that governs.
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={() => {}}
        planCommitments={{ pe: 1.5, pc: 1.2, re: 0.9 }}
        planBasis={{ as_of_quarter: 3, as_of_month: 11, private_weight_reported: 0.31 }}
      />,
    );
    expect(host!.querySelectorAll(".lever-pace").length).toBe(0);
    expect(host!.querySelector(".lever-plan-note")).toBeNull();
    expect(host!.querySelector(".lever-basis")).not.toBeNull();
  });

  it("the four levers stay on the main page between windows, inert", () => {
    const onCommit = vi.fn();
    render(
      <DecisionWindow open={false} month={23} nextStop="Y2 Q4" onCommit={onCommit} />,
    );
    const labels = [...host!.querySelectorAll(".action-card strong")].map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["Hold course", "De-risk", "Lean in", "Secondary sale"]);
    // visible, but there is nothing to commit and nothing to select
    expect(host!.querySelector("button.commit")).toBeNull();
    expect(host!.querySelectorAll('input[type="radio"]').length).toBe(0);
    expect(host!.querySelectorAll(".action-card.inert").length).toBe(4);
    expect(onCommit).not.toHaveBeenCalled();
  });
});

/**
 * D-QC-1 Task A2: the lock sentence. A mid-year quarterly window can still
 * revise the forming vintage's commitment figure; the year-close window
 * locks it. Both sentences are pinned here because the copy is the ONLY
 * thing on screen that tells a player whether typing a number now is
 * provisional or final (spec §4.4's exact wording).
 */
describe("the lock sentence (D-QC-1 Task A2)", () => {
  it("a mid-year window says it locks at the year's Q4, and names the month", () => {
    render(
      <DecisionWindow
        open
        month={14}
        onCommit={() => {}}
        planCommitments={{ pe: 1.5, pc: 1.2, re: 0.9 }}
      />,
    );
    const lock = host!.querySelector(".lever-lock")!.textContent!;
    expect(lock).toBe("This year's commitment locks at Q4 (month 23); until then you can revise it.");
  });

  it("the year-close window itself says it locks now, not 'at Q4'", () => {
    render(
      <DecisionWindow
        open
        month={23}
        onCommit={() => {}}
        planCommitments={{ pe: 1.5, pc: 1.2, re: 0.9 }}
      />,
    );
    const lock = host!.querySelector(".lever-lock")!.textContent!;
    expect(lock).toBe("This year's commitment locks now.");
  });

  it("the heading reads 'This year's commitments', not 'Next year's'", () => {
    render(
      <DecisionWindow
        open
        month={14}
        onCommit={() => {}}
        planCommitments={{ pe: 1.5, pc: 1.2, re: 0.9 }}
      />,
    );
    expect(host!.querySelector(".commit-lever h3")!.textContent).toBe("This year's commitments");
  });

  it("no lock sentence, no crash, when the lever is hidden (stance-only window)", () => {
    // D-QC-1 R-5: months 110/113/116 carry no forming vintage; the server
    // serves next_plan_commitments: null there, and the existing
    // `open && planCommitments` guard hides the whole lever, sentence
    // included.
    render(<DecisionWindow open month={110} onCommit={() => {}} planCommitments={null} />);
    expect(host!.querySelector(".commit-lever")).toBeNull();
    expect(host!.querySelector(".lever-lock")).toBeNull();
  });

  it("the header names the window's own label, not a bare year (D-QC-1 acceptance criterion 6)", () => {
    render(<DecisionWindow open month={5} onCommit={() => {}} />);
    expect(host!.querySelector(".decision-window header h2")!.textContent).toBe(
      "Y1 Q2 — the window is open",
    );
  });
});

/**
 * app-open-02: the band strip that opens above the four action cards while a
 * decision window is OPEN, so "which band am I about to fix or break" is
 * visible at the moment of the decision — not only between windows
 * (BandPanel, Play.tsx). Built on the same `BandSleeve` shape and the same
 * discipline: the served `alert` word is printed verbatim, never
 * re-derived (DN-3 W5).
 */
function bandSleeve(
  sleeve: string,
  opts: {
    target?: number;
    lo?: number;
    hi?: number;
    weight: number;
    alert: AlertLevel;
  },
): BandSleeve {
  return {
    sleeve,
    target: opts.target ?? 35,
    lo: opts.lo ?? 30,
    hi: opts.hi ?? 40,
    true: { weight: opts.weight, alert: opts.alert },
    reported: { weight: opts.weight, alert: opts.alert },
  };
}

describe("DecisionWindow band strip (app-open-02)", () => {
  it("open + report present: rows in server order, alert words verbatim, ranges as lo–hi", () => {
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={() => {}}
        basis="reported"
        bandReport={{
          watch_fraction: 0.5,
          sleeves: [
            bandSleeve("re", { lo: 5, hi: 15, weight: 8, alert: "watch" }),
            bandSleeve("equity", { lo: 30, hi: 40, weight: 44.4, alert: "breach" }),
          ],
        }}
      />,
    );
    const strip = host!.querySelector(".band-strip")!;
    expect(strip).not.toBeNull();
    const rows = [...strip.querySelectorAll(".band-cell")];
    // SERVER order: re, then equity — not alphabetical, not sorted by severity
    expect(rows.map((r) => r.getAttribute("data-sleeve"))).toEqual(["re", "equity"]);
    expect(rows[0].querySelector(".band-badge")!.textContent).toBe("watch");
    expect(rows[1].querySelector(".band-badge")!.textContent).toBe("breach");
    expect(rows[0].querySelector(".band-weight")!.textContent).toBe("8.0");
    expect(rows[1].querySelector(".band-weight")!.textContent).toBe("44.4");
    expect(rows[0].textContent).toContain("5.0–15.0");
    expect(rows[1].textContent).toContain("30.0–40.0");
    // display names, present (ASSET_LABELS lookup, same as BandPanel)
    expect(rows[0].querySelector(".band-name")!.textContent).toBe("Real estate");
    expect(rows[1].querySelector(".band-name")!.textContent).toBe("Equities");
    // the strip sits ABOVE the action cards
    const container = host!.querySelector(".decision-window")!;
    const children = [...container.children];
    expect(children.indexOf(strip)).toBeLessThan(
      children.findIndex((el) => el.className.includes("actions")),
    );
  });

  it("open=false: no strip, even with a report present", () => {
    render(
      <DecisionWindow
        open={false}
        month={23}
        nextStop="Y2 Q4"
        onCommit={() => {}}
        basis="reported"
        bandReport={{
          watch_fraction: 0.5,
          sleeves: [bandSleeve("equity", { weight: 44, alert: "breach" })],
        }}
      />,
    );
    expect(host!.querySelector(".band-strip")).toBeNull();
  });

  it("report null: no strip, no crash, window otherwise unchanged", () => {
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={() => {}}
        basis="reported"
        bandReport={null}
      />,
    );
    expect(host!.querySelector(".band-strip")).toBeNull();
    // the window is otherwise unchanged — the four levers and commit are there
    expect(host!.querySelectorAll('input[type="radio"]').length).toBe(4);
    expect(host!.querySelector("button.commit")).not.toBeNull();
  });

  it("report with an empty sleeve list: no strip", () => {
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={() => {}}
        basis="reported"
        bandReport={{ watch_fraction: 0, sleeves: [] }}
      />,
    );
    expect(host!.querySelector(".band-strip")).toBeNull();
  });

  it("reads the plane matching the session's basis, via planeForBasis — never the reported one on an actual-basis session", () => {
    render(
      <DecisionWindow
        open
        month={11}
        onCommit={() => {}}
        basis="actual"
        bandReport={{
          watch_fraction: 0.5,
          sleeves: [
            {
              sleeve: "equity",
              target: 35,
              lo: 30,
              hi: 40,
              true: { weight: 44.4, alert: "breach" },
              reported: { weight: 33.3, alert: "ok" },
            },
          ],
        }}
      />,
    );
    const row = host!.querySelector(".band-strip .band-cell")!;
    expect(row.querySelector(".band-badge")!.textContent).toBe("breach");
    expect(row.textContent).toContain("44.4");
    expect(row.textContent).not.toContain("33.3");
  });

  it("without a bandReport prop at all, no crash and no strip (default undefined, as every pre-existing test above passes it)", () => {
    render(<DecisionWindow open month={11} onCommit={() => {}} />);
    expect(host!.querySelector(".band-strip")).toBeNull();
  });
});
