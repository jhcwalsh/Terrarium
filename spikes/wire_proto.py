"""
=============================================================================
STATUS: SPIKE. NOT PRODUCTION. NOTHING HERE IS RATIFIED.
=============================================================================
Placement: spikes/ or prototypes/ — NOT the package path. If this file is
importable from production code, that is a defect.

Specifically NOT ratified, and canon by accident if anyone imports them:
  * severity()  — SEV_CUTS and CLASS_SCALE are a FIRST DRAFT for Quant to
                  argue with. DN-9 N-o. The cut-points were tuned to hit a
                  median of ~8 severity-3 events per decade on the TOY path
                  below; they have never been run against a real one.
  * every event threshold in detect()
  * every string in it — placeholder copy, not the editorial golden set
  * the Okun map behind E03 — a derived observable (DN-9 3.4) with no
    registered parameters

synth_path() is a TOY STAND-IN for L1/L2/L3/L4. It is smooth and
well-behaved by construction, which real generated paths are not. Its only
job is to give the narration layer something to narrate.

WHAT THIS FILE IS FOR: proving the pipeline shape — path -> event stream ->
slot contest -> rendered slate — and giving an executable reference so that
ambiguity in DN-9 resolves against something runnable rather than a
paragraph. It already earned that: the episode-semantics defect in
detect() (state conditions firing every period instead of on crossing) was
invisible in prose and obvious on the first calibration run.
=============================================================================

THE WIRE — Tier-1 narration prototype (DN-9)

Proves the pipeline: path -> event stream -> slot contest -> rendered slate.
Deterministic, seeded, no LLM. Tier-1 only.

The path generator here is a TOY STAND-IN for L1/L2/L3/L4. It exists so the
narration layer has something to narrate. It is not the generator and must
never be mistaken for it.

Substantive contribution: severity(), the function DN-9 used ~40 times and
never defined, plus a calibration harness for it (see calibrate()).

    python wire_proto.py            # renders wire_proto.html
    python wire_proto.py --calib    # severity calibration across seeds
"""

import math, random, html, sys
from dataclasses import dataclass, field

T = 120
REGIMES = [("EXP", 1, 24), ("SLOW", 25, 36), ("STAG", 37, 51),
           ("CRI", 52, 57), ("SLOW", 58, 96), ("REF", 97, 120)]


def regime_at(m):
    for name, a, b in REGIMES:
        if a <= m <= b:
            return name
    return "EXP"


# ----------------------------------------------------------------- toy path

def synth_path(seed=4417):
    """Stand-in for L1+L2+L3+L4. Slow states drive fast series."""
    rng = random.Random(seed)
    p = {k: [] for k in ("policy", "cpi", "urate", "eq", "hy", "curve",
                         "cash", "priv_w", "dpi", "regime")}
    pi_star, r_star = 2.2, 1.4
    policy, cpi, urate, eq, hy = 2.50, 2.4, 3.6, 100.0, 320.0
    cash, priv_w, dpi = 3.2, 31.0, 1.02

    for m in range(1, T + 1):
        R = regime_at(m)
        # slow states drift with regime
        pi_star += {"EXP": 0.004, "SLOW": 0.002, "STAG": 0.022,
                    "CRI": -0.030, "REF": -0.006}[R] + rng.gauss(0, .006)
        r_star += {"CRI": -0.012, "SLOW": -0.004}.get(R, 0.001) + rng.gauss(0, .004)

        cpi += (pi_star - cpi) * .06 + rng.gauss(0, .18) + \
               {"STAG": .075, "CRI": -.13, "REF": .012}.get(R, 0)
        cpi = max(0.2, cpi)

        # Taylor-type anchor, smoothed, quantised to 25bp
        cyc = {"EXP": .3, "SLOW": -.25, "STAG": -.15, "CRI": -.75, "REF": .1}[R]
        anchor = r_star + pi_star + 0.55 * (cpi - pi_star) + 0.80 * cyc
        smooth = 0.85 * policy + 0.15 * anchor + rng.gauss(0, .09)
        policy = max(0.0, round(smooth * 4) / 4)

        urate += {"EXP": -.02, "SLOW": .035, "STAG": .015,
                  "CRI": .16, "REF": -.03}[R] + rng.gauss(0, .05)
        urate = max(2.8, urate)

        drift, vol = {"EXP": (.009, .030), "SLOW": (.001, .038),
                      "STAG": (-.004, .048), "CRI": (-.043, .085),
                      "REF": (.011, .034)}[R]
        eq *= (1 + drift + rng.gauss(0, vol))

        hy_t = {"EXP": 320, "SLOW": 430, "STAG": 470,
                "CRI": 880, "REF": 300}[R]
        hy += (hy_t - hy) * .14 + rng.gauss(0, 16)
        curve = 1.9 - 0.55 * (policy - r_star - pi_star) * 2.2 + rng.gauss(0, .15)

        # the book
        dist = {"EXP": 1.02, "SLOW": .80, "STAG": .88,
                "CRI": .70, "REF": 1.35}[R] + rng.gauss(0, .05)
        dpi += (dist - dpi) * .3
        cash += (dpi - 1.0) * 1.1 - 0.12 + rng.gauss(0, .09)
        pub_ret = drift + rng.gauss(0, vol)
        priv_w += -pub_ret * 26 + rng.gauss(0, .12)      # denominator effect
        if cash < 0:
            cash += 2.6                                  # forced sale replenishes

        for k, v in dict(policy=policy, cpi=cpi, urate=urate, eq=eq, hy=hy,
                         curve=curve * 100, cash=cash, priv_w=priv_w,
                         dpi=dpi, regime=R).items():
            p[k].append(v)
    return p


# ------------------------------------------------------------- severity ***

# DN-9 left `severity` undefined. First draft, for Quant to argue with.
#
#   1. Normalise every trigger to a z-score on a common scale
#   2. Band it 0..3 on fixed cut-points
#   3. Class-specific scale factors, so a 2-sigma CPI print and a 2-sigma
#      spread move are comparable
#   4. Hard overrides where the event IS the severity (gating, forced sale)

SEV_CUTS = (1.0, 2.0, 3.0)
CLASS_SCALE = {                 # divides |z|; >1 damps, <1 amplifies
    "E01": 0.8, "E02": 1.0, "E03": 1.1, "E05": 1.0, "E07": 1.2,
    "E08": 0.9, "E10": 0.7, "E11": 1.1, "E12": 1.0, "E15": 0.9,
    "E16": 1.0, "E18": 1.0, "E19": 1.4,
}
HARD = {"E16": 3, "E18": 3}


def severity(cls, z):
    if cls in HARD:
        return HARD[cls]
    a = abs(z) / CLASS_SCALE.get(cls, 1.0)
    return 0 if a < SEV_CUTS[0] else 1 if a < SEV_CUTS[1] else 2 if a < SEV_CUTS[2] else 3


def zs(series, m, win=24):
    lo = max(0, m - win)
    w = series[lo:m]
    if len(w) < 6:
        return 0.0
    mu = sum(w) / len(w)
    sd = (sum((x - mu) ** 2 for x in w) / len(w)) ** .5 or 1e-9
    return (series[m] - mu) / sd


# ---------------------------------------------------------------- events

@dataclass
class Event:
    month: int; cls: str; slot: str; sev: int
    headline: str; body: str
    chips: tuple = ()
    trig: dict = field(default_factory=dict)


def pct(series, m):
    return (series[m] / series[m - 1] - 1) if m else 0.0


def detect(p, seed):
    rng = random.Random(seed ^ 0xA5)
    ev = []
    # Episode state. DN-9 §3.1 as written treats every class as a point event.
    # Classes describing a sustained CONDITION (drawdown, drought, gating,
    # forced sale) must fire on episode onset or milestone crossing, never on
    # every period the condition holds. Same defect class as the WP3.9
    # forced-sale rule. See MILESTONES below.
    dd_reached = 0        # deepest drawdown milestone hit this episode
    in_forced = False
    MILESTONES = (0.10, 0.20, 0.30, 0.40)
    for m in range(1, T):
        R = p["regime"][m]

        # E01 policy — quarter-end meetings
        if m % 3 == 2:
            d = p["policy"][m] - p["policy"][m - 1]
            eps = d + rng.gauss(0, .06)
            s = severity("E01", eps / 0.18)
            verb = "raises" if d > 0.01 else "lowers" if d < -0.01 else "holds"
            if verb == "holds":
                head = f"Committee holds at {p['policy'][m]:.2f}%"
                body = ("No change, and the balance-of-risks sentence survives intact. "
                        "The rule implies the Committee is close to where it wants to be.")
            else:
                head = (f"Committee {verb} to {p['policy'][m]:.2f}%"
                        + (", and the statement hardens" if d > 0 else ", first move of the turn"))
                body = (f"A move of {abs(d)*100:.0f} basis points against a rule that implied "
                        f"{p['policy'][m]-eps:.2f}%. The residual is judgement, not arithmetic.")
            ev.append(Event(m, "E01", "POLICY", s, head, body,
                            (("SURPRISE" if abs(eps) > .15 else "IN LINE"),
                             "HAWKISH" if eps > 0 else "DOVISH"),
                            {"policy": p["policy"][m], "eps": round(eps, 3)}))

        # E02 inflation
        z = zs(p["cpi"], m)
        cons = p["cpi"][m - 1] + (p["cpi"][m - 1] - p["cpi"][m - 2]) * .5 if m > 2 else p["cpi"][m]
        surp = p["cpi"][m] - cons
        ev.append(Event(m, "E02", "DATA", severity("E02", surp / 0.30),
                        f"Inflation {'rises to' if surp>0 else 'eases to'} {p['cpi'][m]:.1f}%",
                        f"Consensus looked for {cons:.1f}%. Services led; goods "
                        f"{'stopped helping' if surp>0 else 'continued to help'}.",
                        (f"{'ABOVE' if surp>0 else 'BELOW'} {abs(surp)/0.3:+.1f}σ",
                         "HAWKISH" if surp > 0 else "DOVISH"),
                        {"cpi": round(p["cpi"][m], 2), "consensus": round(cons, 2)}))

        # E03 labour (derived observable)
        zu = zs(p["urate"], m)
        ev.append(Event(m, "E03", "DATA", severity("E03", zu),
                        f"Unemployment {'rises to' if zu>0 else 'holds at'} {p['urate'][m]:.1f}%",
                        "Derived from the trend-growth state by a fixed Okun map. "
                        + ("The labour market has refused to soften on schedule."
                           if zu < 0 else "The softening the Committee forecast has arrived."),
                        (f"{'ABOVE' if zu>0 else 'BELOW'} {abs(zu):+.1f}σ",
                         "DOVISH" if zu > 0 else "HAWKISH"),
                        {"urate": round(p["urate"][m], 2)}))

        # E05 / E10 equity
        r = pct(p["eq"], m)
        peak = max(p["eq"][:m + 1])
        dd = p["eq"][m] / peak - 1
        crossed = 0
        for k, lvl in enumerate(MILESTONES, start=1):
            if -dd >= lvl and k > dd_reached:
                crossed = k
        if p["eq"][m] >= peak - 1e-9:
            dd_reached = 0                      # new high ends the episode
        if crossed:
            dd_reached = crossed
            ev.append(Event(m, "E10", "MARKETS", min(3, crossed + 1),
                            f"Equities pass {MILESTONES[crossed-1]*100:.0f}% below the peak",
                            "The drawdown has crossed a level that has historically "
                            "preceded a change in the Committee's language.",
                            (f"{dd*100:.0f}% FROM PEAK", "RISK-OFF"), {"dd": round(dd, 3)}))
        else:
            ev.append(Event(m, "E05", "MARKETS", severity("E05", r / 0.035),
                            f"Equities {'add' if r>0 else 'give up'} {abs(r)*100:.1f}%",
                            "The move was concentrated in the sessions following the print.",
                            (f"{r*100:+.1f}%", "RISK-ON" if r > 0 else "RISK-OFF"),
                            {"r": round(r, 4)}))

        # E08 credit
        dh = p["hy"][m] - p["hy"][m - 1]
        if abs(dh) > 25:
            ev.append(Event(m, "E08", "MARKETS", severity("E08", dh / 45),
                            f"High yield {'widens' if dh>0 else 'tightens'} to {p['hy'][m]:.0f}bp",
                            f"A move of {abs(dh):.0f} basis points on the month, "
                            f"{'the fastest in the series' if abs(dh)>90 else 'orderly by recent standards'}.",
                            (f"{dh:+.0f}BP", "RISK-OFF" if dh > 0 else "RISK-ON"),
                            {"hy": round(p["hy"][m])}))

        # E15 / E18 the book
        forced = p["cash"][m] < 0.15 and p["dpi"][m] < 0.75
        if forced and not in_forced:
            in_forced = True
            ev.append(Event(m, "E18", "CAPITAL", 3,
                            "Endowment forced to sell into the drought",
                            f"Distributions at {p['dpi'][m]:.2f}× plan with cash exhausted. "
                            "Listed sleeves were sold first; the balance cleared as a "
                            "secondary at a discount to carrying value.",
                            ("FORCED SALE", "DETERIORATING"),
                            {"cash": round(p["cash"][m], 2), "dpi": round(p["dpi"][m], 2)}))
        elif R != "EXP":
            if not forced:
                in_forced = False
            zd = (p["dpi"][m] - 1.0) / 0.22
            ev.append(Event(m, "E15", "CAPITAL", severity("E15", zd),
                            f"Distributions at {p['dpi'][m]:.2f}× the pacing plan",
                            f"Cash {p['cash'][m]:.1f}% of assets. Private weight "
                            f"{p['priv_w'][m]:.1f}% — the increase came from public markets "
                            "falling, not from anything the institution did.",
                            (f"DPI {p['dpi'][m]:.2f}×",
                             "DETERIORATING" if zd < -0.5 else "NEUTRAL"),
                            {"dpi": round(p["dpi"][m], 2)}))
        else:
            ev.append(Event(m, "E19", "CAPITAL", severity("E19", 1.2),
                            "Heavy quarter for fund formation",
                            f"Distributions at {p['dpi'][m]:.2f}× plan. Cash "
                            f"{p['cash'][m]:.1f}%. Underwriting standards, one placement "
                            "agent conceded, are a conversation nobody is enjoying.",
                            (f"DPI {p['dpi'][m]:.2f}×", "STRENGTHENING"), {}))
    return ev


# ------------------------------------------------------------- slate contest

def slates(ev):
    out = {}
    for e in ev:
        q = (e.month - 1) // 3 + 1
        out.setdefault(q, {}).setdefault(e.slot, []).append(e)
    res = {}
    for q, slots in out.items():
        picked = {}
        for slot, cand in slots.items():
            # deterministic contest: severity, then latest month
            picked[slot] = sorted(cand, key=lambda e: (e.sev, e.month))[-1]
        # a quiet quarter drops CAPITAL
        if picked.get("CAPITAL") and picked["CAPITAL"].sev == 0 and \
           max(e.sev for e in picked.values()) <= 1:
            picked.pop("CAPITAL")
        res[q] = picked
    return res


# ---------------------------------------------------------------- rendering

CSS = """
body{background:#f6f2e9;font-family:Georgia,'Times New Roman',serif;margin:0;padding:32px;color:#14181d}
.page{max-width:1040px;margin:0 auto 40px;background:#fdfcf8;border:1px solid #ded6c7;padding:28px 32px}
.mast{text-align:center;font-size:34px;letter-spacing:7px;margin:4px 0 10px}
.rule{border-top:2.4px solid #14181d;border-bottom:.8px solid #14181d;height:3px;margin-bottom:10px}
.dateline{display:flex;justify-content:space-between;font-size:12px;color:#5c6570;font-style:italic;margin-bottom:14px}
.dash{background:#f0ebe0;border:1px solid #ded6c7;display:flex;padding:12px 0;margin-bottom:20px}
.dash div{flex:1;padding:0 16px;border-right:1px solid #ded6c7}
.dash div:last-child{border:0}
.dash .lbl{font-size:9.5px;letter-spacing:2.5px;color:#5c6570}
.dash .big{font-size:16px;margin:5px 0 3px}
.dash .sub{font-size:11px;color:#2b3238}
.lead{border:1.2px solid #14181d;padding:0 0 16px}
.slot{background:#14181d;color:#fdfcf8;font-size:9.5px;letter-spacing:3px;padding:5px 12px;display:flex;justify-content:space-between}
.lead h1{font-size:30px;margin:16px 18px 8px;line-height:1.12}
.lead p{margin:0 18px;font-size:13px;color:#2b3238}
.cards{display:flex;gap:16px;margin-top:16px}
.card{flex:1;border:1px solid #ded6c7}
.card .slot{background:#f0ebe0;color:#5c6570}
.card h2{font-size:18px;margin:12px 14px 8px;line-height:1.15}
.card p{margin:0 14px 12px;font-size:11.5px;color:#2b3238}
.chip{background:#8f2e26;color:#fdfcf8;padding:1px 7px;font-size:8.5px;letter-spacing:1px;margin-left:5px}
.chip.n{background:#e6ded0;color:#2b3238}
.special{background:#14181d;color:#fdfcf8;text-align:center;font-size:11px;letter-spacing:5px;padding:5px;margin-bottom:10px}
.foot{border-top:.8px solid #14181d;margin-top:20px;padding-top:10px;font-size:9.5px;color:#5c6570;display:flex;justify-content:space-between}
"""


def chip(c, i):
    return f'<span class="chip{" n" if i==0 else ""}">{html.escape(c)}</span>'


def render(p, sl, quarters):
    o = [f"<html><head><meta charset='utf-8'><title>THE WIRE</title><style>{CSS}</style></head><body>"]
    for q in quarters:
        picked = sl.get(q, {})
        if not picked:
            continue
        m = min(q * 3, T) - 1
        yr, qn = (q - 1) // 4 + 1, (q - 1) % 4 + 1
        special = any(e.sev >= 3 for e in picked.values())
        o.append("<div class='page'>")
        o.append("<div class='mast'>THE WIRE</div><div class='rule'></div>")
        if special:
            o.append("<div class='special'>SPECIAL EDITION</div>")
        o.append(f"<div class='dateline'><span>Year {yr}, Quarter {qn} · "
                 f"regime {p['regime'][m]}</span><span>Second Wind · slate sw-4417-q{q}</span></div>")
        o.append("<div class='dash'>"
                 f"<div><div class='lbl'>POLICY &amp; RATES</div><div class='big'>{p['policy'][m]:.2f}%</div>"
                 f"<div class='sub'>2s10s {p['curve'][m]:.0f}bp</div></div>"
                 f"<div><div class='lbl'>MACRO</div><div class='big'>CPI {p['cpi'][m]:.1f}%</div>"
                 f"<div class='sub'>Unemployment {p['urate'][m]:.1f}%</div></div>"
                 f"<div><div class='lbl'>PUBLIC MARKETS</div><div class='big'>{p['eq'][m]:.0f}</div>"
                 f"<div class='sub'>HY OAS {p['hy'][m]:.0f}bp</div></div>"
                 f"<div><div class='lbl'>THE BOOK</div><div class='big'>cash {p['cash'][m]:.1f}%</div>"
                 f"<div class='sub'>priv {p['priv_w'][m]:.1f}% · DPI {p['dpi'][m]:.2f}×</div></div></div>")

        order = sorted(picked.values(), key=lambda e: -e.sev)
        lead, rest = order[0], order[1:]
        o.append(f"<div class='lead'><div class='slot'><span>{lead.slot} · sev {lead.sev}</span>"
                 f"<span>{''.join(chip(c,i) for i,c in enumerate(lead.chips))}</span></div>"
                 f"<h1>{html.escape(lead.headline)}</h1><p>{html.escape(lead.body)}</p></div>")
        o.append("<div class='cards'>")
        for e in rest:
            o.append(f"<div class='card'><div class='slot'><span>{e.slot} · sev {e.sev}</span>"
                     f"<span>{''.join(chip(c,i) for i,c in enumerate(e.chips))}</span></div>"
                     f"<h2>{html.escape(e.headline)}</h2><p>{html.escape(e.body)}</p></div>")
        o.append("</div>")
        o.append("<div class='foot'><span>SIMULATED WORLD · no firm or person is real · "
                 "not investment advice</span><span>Tier-1 · deterministic · no LLM</span></div></div>")
    o.append("</body></html>")
    return "\n".join(o)


# -------------------------------------------------------------- calibration

def calibrate(n=200):
    """Severity cut-points are a real parameter. Calibrate against the ensemble:
    a median decade should produce a target count of severity-3 events."""
    counts = []
    for s in range(n):
        ev = detect(synth_path(4000 + s), 4000 + s)
        counts.append(sum(1 for e in ev if e.sev == 3))
    counts.sort()
    print(f"severity-3 events per decade, {n} seeds")
    for q, lbl in ((0.05, "p5"), (0.25, "p25"), (0.5, "median"), (0.75, "p75"), (0.95, "p95")):
        print(f"  {lbl:>6}: {counts[int(q*(n-1))]:>4}")
    print(f"\n  cut-points {SEV_CUTS} -> median {counts[n//2]} severity-3 events/decade")
    print("  Target band is a product decision. Too many and every quarter is a")
    print("  crisis; too few and nothing ever happens. Recommend 4-10.")


if __name__ == "__main__":
    if "--calib" in sys.argv:
        calibrate()
    else:
        p = synth_path(4417)
        sl = slates(detect(p, 4417))
        qs = [7, 15, 18, 21]          # quiet · the turn · the crisis · the drought
        open("wire_proto.html", "w").write(render(p, sl, qs))
        tot = sum(len(v) for v in sl.values())
        print(f"rendered {len(qs)} slates -> wire_proto.html  ({tot} announcements across 40 slates)")
