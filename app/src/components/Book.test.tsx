import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { Book, PRIVATE_BAND } from "./Book";
import type { Session } from "../lib/session";

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

const base: Session = {
  session_id: "s", run_id: "r", world_id: "w", months: 120, revealed_months: 24,
  basis: "reported", ranked: false, participant: null, decisions: {},
  window_log: [], status: "active",
  value: 96.2, twin_value: 95.1, cash: 2.4, coverage_true: 0.31,
  coverage_reported: 0.29, private_weight_true: 0.36,
};

describe("Book", () => {
  it("shows cash and the book's value", () => {
    render(<Book session={base} />);
    expect(host!.textContent).toContain("2.4");
    expect(host!.textContent).toContain("96.2");
  });

  it("flags a private-weight breach, and does not cry wolf inside the band", () => {
    render(<Book session={base} />);
    expect(host!.querySelector(".band-breach")).toBeNull();

    act(() => root!.render(<Book session={{ ...base, private_weight_true: 0.44 }} />));
    expect(host!.querySelector(".band-breach")).not.toBeNull();
    expect(PRIVATE_BAND).toEqual([0.15, 0.4]);
  });

  it("labels Value with the session's fixed basis and Coverage/Private weight as true basis, so it never shows an unexplained number beside the CIO dashboard's plane-driven figures", () => {
    render(<Book session={base} />);
    expect(host!.textContent).toMatch(/value.*reported basis/i);
    expect(host!.textContent).toMatch(/coverage.*true basis/i);
    expect(host!.textContent).toMatch(/private weight.*true basis/i);

    act(() => root!.render(<Book session={{ ...base, basis: "actual" }} />));
    expect(host!.textContent).toMatch(/value.*actual basis/i);
  });

  it("states the reported-vs-true gap rather than hiding it", () => {
    render(<Book session={{ ...base, coverage_true: 0.31, coverage_reported: 0.29 }} />);
    expect(host!.textContent).toMatch(/reported/i);
    expect(host!.textContent).toMatch(/true/i);
  });

  it("renders before the first quarter closes without throwing", () => {
    render(<Book session={{ ...base, revealed_months: 1, value: null, cash: null }} />);
    expect(host!.textContent).toBeTruthy();
  });
});
