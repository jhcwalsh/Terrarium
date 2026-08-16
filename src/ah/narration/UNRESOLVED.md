# UNRESOLVED — the narration workbench's open parameters

*Generated from `src/ah/narration/params.py` by `render_unresolved_md()`. Do not edit by hand; edit the registry and regenerate. `tests/test_narration_params.py` asserts the two agree.*

Every entry below is a value the workbench build needed and `voices.yaml` does not resolve. The build does **not** proceed on a default: loading an `UNRESOLVED` key raises `UnresolvedParameter` and the run fails with this list.

**Nothing here has been decided, and the ordering of `candidates` is not a ranking.** Candidates are the values someone would choose between, in the order DN-9 or the `voices.yaml` skeleton raises them.

**62 open parameters.** 7 of them are gated on inputs the workbench world does not carry (marked *gated*) and were not on the critical path of the first build; they are open all the same.

---

## `severity.cuts`

*Register: A3-B (severity cut-points).*

- **Needed for:** severity(): banding |z| onto 0..3 for every event class.
- **Depends on it:** the severity-3 count per decade, whether SPECIAL fires and displaces the front page, headline size, and every slot contest that is decided on severity.
- **Candidates:** `[1.0, 2.0, 3.0]` · `[1.25, 2.25, 3.25]` · `[1.5, 2.5, 3.5]`.
- **Trade-off:** Lower cuts make the decade dramatic and the SPECIAL band common; higher cuts make severity-3 genuinely rare but risk a crisis quarter reading as ordinary. The spike's [1.0, 2.0, 3.0] were tuned on a TOY path and have never been run against a generated one, so they are a candidate, not a starting point.

## `severity.target_sev3_band`

*Register: A3-B (severity cut-points).*

- **Needed for:** the diagnostics severity-calibration panel's pass/fail statement.
- **Depends on it:** whether a build is declared calibrated; it does not change any copy.
- **Candidates:** `[4, 10]` · `[6, 14]` · `[3, 8]`.
- **Trade-off:** [4, 10] is the spike's recommendation and implies roughly one severity-3 event per year; [6, 14] tolerates a busier decade and will accept cut-points that [4, 10] rejects. The band is a product decision about how eventful a world should feel, and it is the number the calibration panel is judged against.

## `severity.class_scale`

*Register: A3-B (per-class scales).*

- **Needed for:** severity(): the per-class divisor that makes a 2-sigma CPI print and a 2-sigma spread move comparable.
- **Depends on it:** the relative prominence of each class in the slot contests.
- **Candidates:** `{'E01': 0.8, 'E02': 1.0, 'E03': 1.1, 'E04': 1.1, 'E05': 1.0, 'E06': 1.0, 'E07': 1.2, 'E08': 0.9, 'E09': 1.2, 'E10': 0.7, 'E11': 1.1, 'E21': 1.4}` · `{'E01': 1.0, 'E02': 1.0, 'E03': 1.0, 'E04': 1.0, 'E05': 1.0, 'E06': 1.0, 'E07': 1.0, 'E08': 1.0, 'E09': 1.0, 'E10': 1.0, 'E11': 1.0, 'E21': 1.0}`.
- **Trade-off:** The first is the spike's draft, which damps policy and drawdown (<1 amplifies) so that market moves do not crowd them out. The second is the null: no class privileged, all comparability carried by the z-score alone — defensible, and it will let a noisy class dominate MARKETS every quarter. This map is the single largest lever on which class wins which slot.

## `severity.z_window_months`

*Register: A3-B (severity cut-points).*

- **Needed for:** the trailing window every z-score and sigma-hat is computed over.
- **Depends on it:** every severity, every consensus, every surprise in sigma units.
- **Candidates:** `24` · `36` · `60`.
- **Trade-off:** 24 months makes the paper adapt fast — a long calm makes small moves look large, which is arguably right and arguably a bug. 60 months holds a single reference frame across a whole regime, so a crisis stays large for years. The window also sets how long a world must run before anything can fire.

## `events.E01.threshold`

- **Needed for:** E01 policy decision: the |epsilon| scale, in percentage points, that normalises the smoothed-anchor residual to a z.
- **Depends on it:** which meetings are surprises, the FOMC set-piece's tone, dissent copy.
- **Candidates:** `0.18` · `0.25` · `0.125`.
- **Trade-off:** 0.125 is half a 25bp step, so any move the anchor did not imply reads as a surprise; 0.25 is a whole step and reserves the word for a genuine repricing. The spike used 0.18 with no stated derivation.

## `events.E02.threshold`

- **Needed for:** E02 inflation print: the surprise scale in percentage points.
- **Depends on it:** DATA-slot contests, verdict chips, the three-beat data day.
- **Candidates:** `0.3` · `0.2` · `0.5`.
- **Trade-off:** 0.20 makes most prints newsworthy and the DATA slot busy; 0.50 reserves it for the print that ends an argument (DN-9 §A.2). This interacts with consensus.dispersion — the two together decide what a 'sigma' means on the page.

## `events.E03.threshold`

- **Needed for:** E03 labour print: the unemployment surprise scale in percentage points.
- **Depends on it:** whether the derived labour print ever beats CPI for the DATA slot.
- **Candidates:** `0.2` · `0.1` · `0.3`.
- **Trade-off:** The labour print is a derived observable (DN-9 §3.4), so this threshold is measuring a transform's output, not a market. Set it tight and payrolls day wins the DATA slot most quarters; set it loose and the most dramatic release on the real calendar never leads.

## `events.E04.threshold`

- **Needed for:** E04 growth print: the surprise scale in annualised percentage points.
- **Depends on it:** the quarterly DATA slot when neither CPI nor labour surprises.
- **Candidates:** `0.5` · `0.25` · `1.0`.
- **Trade-off:** Quarterly growth is the least surprising of the three prints because it is the state variable the other two are derived from; too tight a threshold makes it fire on the transform's own noise.

## `events.E05.threshold`

- **Needed for:** E05 equity move: k in |r| > k * sigma-hat (DN-9 §3.2).
- **Depends on it:** how many months carry a market lead at all.
- **Candidates:** `1.5` · `2.0` · `1.0`.
- **Trade-off:** 1.0 fires roughly a third of months and makes the MARKETS slot a monthly return report; 2.0 fires a handful of times a decade and leaves quiet quarters with no MARKETS candidate, which pushes slate size down to three slots.

## `events.E06.threshold`

- **Needed for:** E06 rate move: the 10y monthly change band, in basis points.
- **Depends on it:** whether rates ever take the MARKETS slot from equities.
- **Candidates:** `25` · `40` · `15`.
- **Trade-off:** A band, not a z-score, because the reader's sense of a big yield move is absolute rather than relative — but a fixed band behaves very differently in a 1970s-class world than in a 2010s one, which is the argument for 40bp here and for making it a spec parameter rather than a constant.

## `events.E07.threshold`

- **Needed for:** E07 curve inversion/re-steepening: the dead-zone around zero, in basis points, a sign change must clear to count.
- **Depends on it:** the episode count for the curve; chatter around a flat curve.
- **Candidates:** `0` · `5` · `10`.
- **Trade-off:** 0 is the literal reading of DN-9 ('sign change on 2s10s') and will fire twice a month while the curve sits at zero — the episode grouping makes that two episodes, not twenty events, but it is still two announcements. A 5-10bp dead zone is what a desk would use and costs a defensible arbitrary number.

## `events.E08.threshold`

- **Needed for:** E08 credit spread breach: the HY OAS tier ladder, in basis points.
- **Depends on it:** the credit lead, and the highest-severity event in most crisis quarters.
- **Candidates:** `[400, 600, 800]` · `[300, 500, 700, 900]` · `[350, 500, 750]`.
- **Trade-off:** DN-9 says 'crosses tier' without saying where the tiers are. A three-rung ladder maps cleanly onto severity 1/2/3; a four-rung one gives the crisis somewhere further to go. Absolute levels are regime-dependent in exactly the way the E06 band is, and a 1970s world sits above 400bp for years.

## `events.E09.threshold`

- **Needed for:** E09 volatility regime: the cut-points on annualised equity vol that define the vol state.
- **Depends on it:** the 'vol: quiet, 11 months' furniture on the market strip; E09 episodes.
- **Candidates:** `[15, 25]` · `[12, 20, 30]` · `[18, 28]`.
- **Trade-off:** Two cuts give quiet/ordinary/elevated; three give a fourth 'extreme' state that the dislocated layout can key off. More states means more transitions means more episodes, and E09 is a state class so each transition is an announcement.

## `events.E10.milestones`

- **Needed for:** E10 drawdown: the peak-to-trough crossings that fire, as fractions.
- **Depends on it:** the special-edition band; the run's defining market headlines.
- **Candidates:** `[0.1, 0.2, 0.3]` · `[0.1, 0.2, 0.3, 0.4]` · `[0.15, 0.25, 0.35]`.
- **Trade-off:** DN-9 §3.2 names -10/-20/-30 explicitly, so the first candidate is the note's own and is here as a candidate rather than a default only because the fourth rung matters in a world that draws down further. Milestones are crossings: an episode fires each rung once, and a new high resets.

## `events.E11.threshold`

- **Needed for:** E11 recovery milestone: the minimum prior drawdown, as a fraction, that makes a new high newsworthy.
- **Depends on it:** whether the recovery is reported at all.
- **Candidates:** `0.2` · `0.1` · `0.15`.
- **Trade-off:** DN-9 §3.2 says 'new high after >= 20% drawdown'. 0.10 makes recoveries routine and gives the MARKETS slot a positive story more often, which matters because a bank of only negative market copy reads as editorialising.

## `events.E12.threshold`

- **Needed for:** E12 private mark update: the quarter-close reported-mark move, in percentage points, that is worth a correction box.
- **Depends on it:** the correction box (DN-9 §4.3), the CAPITAL slot on quarter months.
- **Gated on:** the optional book series (cash_pct, dpi_vs_plan, calls, distributions).
- **Candidates:** `1.0` · `0.5` · `2.0`.
- **Trade-off:** The correction box is DN-9's uniquely-ours mechanic and its whole force is that it is small and dry; too low a threshold prints one every quarter and the joke stops working.

## `events.E15.threshold`

- **Needed for:** E15 distribution drought: the rolling distribution rate, as a multiple of plan, below which a drought episode opens.
- **Depends on it:** the drought feature; the slow story that outlasts the equity recovery.
- **Gated on:** the optional book series (cash_pct, dpi_vs_plan, calls, distributions).
- **Candidates:** `0.75` · `0.85` · `0.6`.
- **Trade-off:** The drought is the DN-9 specimen world's real damage and it arrives as an absence. A high trigger opens an episode in every ordinary slowdown; a low one means the paper only notices once the cash account is already in trouble.

## `events.E16.threshold`

- **Needed for:** E16 gating: the redemption-queue percentage that constitutes a gate.
- **Depends on it:** a hard severity-3 override, so directly on the SPECIAL band.
- **Gated on:** the optional book series (cash_pct, dpi_vs_plan, calls, distributions).
- **Candidates:** `1.0` · `0.5` · `0.25`.
- **Trade-off:** A full gate (queue 100%) is unambiguous; a partial queue is the more common real event and the more interesting one, but it needs a line drawn somewhere and the line is the whole event.

## `events.E17.threshold`

- **Needed for:** E17 secondary pricing: the discount-tier change, in percentage points of NAV, that fires.
- **Depends on it:** the market strip and the secondaries feature.
- **Gated on:** the optional book series (cash_pct, dpi_vs_plan, calls, distributions).
- **Candidates:** `10.0` · `5.0` · `15.0`.
- **Trade-off:** Secondary discounts move in steps that are large but infrequent; a tight threshold turns a quarterly print into a monthly one and the series does not support that.

## `events.E18.threshold`

- **Needed for:** E18 forced sale: the cash-waterfall breach, as a fraction of assets, that opens a forced-sale episode.
- **Depends on it:** the run's defining headline; CAPITAL outright per DN-9 §B.11 rule 6.
- **Gated on:** the optional book series (cash_pct, dpi_vs_plan, calls, distributions).
- **Candidates:** `0.0` · `0.005` · `0.01`.
- **Trade-off:** 0.0 means the sale is reported when cash actually runs out, which is what WP3.9's waterfall models; a small positive buffer reports the institution as a forced seller slightly before it is one, which is arguably the honest reading and is arguably the paper knowing something it should not.

## `events.E19.threshold`

- **Needed for:** E19 fund formation: the commitment-pacing z above which the business section notices.
- **Depends on it:** the quiet-quarter CAPITAL slot — the only routine good news in the bank.
- **Gated on:** the optional book series (cash_pct, dpi_vs_plan, calls, distributions).
- **Candidates:** `1.0` · `1.5` · `0.5`.
- **Trade-off:** This is the class that fills the CAPITAL slot when nothing is wrong, so a high threshold does not make the paper quieter — it makes quiet quarters drop to three slots.

## `slate.contest_rule`

*Register: A3-B, N-o.*

- **Needed for:** slate assembly: how the candidates for one slot are ordered.
- **Depends on it:** which announcement the reader sees; the slot-contest diagnostics panel.
- **Candidates:** `severity_then_abs_delta` · `severity_then_latest_month` · `severity_then_earliest_month`.
- **Trade-off:** DN-9 §B.1 gives per-slot rules in words (POLICY on |epsilon|, DATA on largest |surprise_sd|, MARKETS and CAPITAL on severity) but no general rule. 'severity_then_abs_delta' reproduces all four in one sentence, because each slot's stated tie-break IS its delta magnitude. 'latest' privileges the freshest news and will systematically drop the third month of a quarter's own lead; 'earliest' does the reverse.

## `slate.tie_break`

*Register: A3-B, N-o.*

- **Needed for:** slate assembly: resolving an exact tie under the contest rule.
- **Depends on it:** determinism — the alternative is dict or set ordering, which is a defect.
- **Candidates:** `lowest_class_id_then_lowest_month` · `lowest_month_then_lowest_class_id` · `highest_abs_delta_then_lowest_class_id`.
- **Trade-off:** All three are deterministic and documented, which is the requirement; they differ in what they privilege when two events are genuinely equal. Class-id order is arbitrary but stable and makes the same class win every tie — which is visible in the slot-contest panel as a class hogging a slot.

## `slate.min_slots`

*Register: A3-B, N-o.*

- **Needed for:** slate assembly: the three-versus-four-slot threshold (DN-9 §B.1).
- **Depends on it:** slate size, which must be a function of the quarter's own events only.
- **Candidates:** `3` · `4` · `2`.
- **Trade-off:** DN-9 says quiet quarters run three slots and that slate size must never be a forward signal. 4 forces a fourth announcement even where nothing anchors it, which violates §B.2; 2 lets a genuinely empty quarter shrink further and makes slate size a more legible signal of how quiet the quarter was.

## `slate.capital_drop_rule`

*Register: A3-B, N-o.*

- **Needed for:** slate assembly: when the CAPITAL slot is dropped for a quiet quarter.
- **Depends on it:** slate size; DN-9 §B.1 'dropped when nothing in the book moved beyond routine'.
- **Gated on:** the optional book series (cash_pct, dpi_vs_plan, calls, distributions).
- **Candidates:** `drop_when_max_severity_zero` · `drop_when_max_severity_below_one` · `never_drop`.
- **Trade-off:** 'Beyond routine' is not defined. Dropping only on an all-zero book is conservative and keeps CAPITAL present almost always; dropping below severity 1 makes three-slot quarters common and the four-slot quarter meaningful.

## `voices.fomc.anchor.rho`

*Register: A3-B, N-p.*

- **Needed for:** the smoothed narration anchor i~_t = rho*i_{t-1} + (1-rho)*anchor_t.
- **Depends on it:** every epsilon, therefore every policy verdict, the statement's tone, the dissent count and the strain score.
- **Candidates:** `0.85` · `0.7` · `0.9`.
- **Trade-off:** DN-9 §C.6 reports 0.85 turning an unusable +1.47 residual into +0.01 on the worked cut, but explicitly says rho is to be ESTIMATED ONCE, FROZEN AND STAMPED — an inherited 0.85 is the number from a worked example on a different world. Lower rho tracks the rule and produces large residuals whenever the rule level moves; higher rho makes almost every meeting look anticipated.

## `voices.fomc.anchor.quantise_bp`

*Register: A3-B.*

- **Needed for:** display quantisation of the anchor and the realised path (DN-9 §C.6).
- **Depends on it:** whether the statement can explain the decision at all.
- **Candidates:** `25` · `12.5` · `0`.
- **Trade-off:** 25bp is what a policy rate does and is what turns 5.05 into 5.00. 0 means no quantisation and the FOMC set-piece narrates arbitrary increments, which §C.6 says is unbuildable. This is a display transform under §3.4 and is registered as one; it is NOT a fix for an un-inertial generated path, which is referral N-q.

## `voices.fomc.anchor.phi_pi`

*Register: A3-B, N-p.*

- **Needed for:** the inflation-gap coefficient in the DN-1 II.2 anchor decomposition.
- **Depends on it:** the rule-monitor sidebar's arithmetic, and therefore epsilon.
- **Candidates:** `0.55` · `0.5` · `1.5`.
- **Trade-off:** 0.55 is the value DN-9 §C.5 works the example at; 0.5 is the Taylor original; 1.5 is the Taylor principle on the gap rather than the level and implies a much more aggressive rule. The generator does not emit this coefficient — the anchor is narration's own reconstruction — so it must be stated and stamped, and a wrong value shows up as strain rather than as an error.

## `voices.fomc.anchor.phi_c`

*Register: A3-B, N-p.*

- **Needed for:** the cycle coefficient in the anchor decomposition.
- **Depends on it:** the rule monitor; epsilon; the 'the slowdown argues for an offset' clause.
- **Candidates:** `0.8` · `0.5` · `1.0`.
- **Trade-off:** Same standing as phi_pi: 0.80 is the §C.5 worked value. The larger it is, the more of a cut the rule explains by itself and the smaller the residual the Committee is credited with.

## `voices.fomc.anchor.cycle_source`

*Register: A3-B, N-p.*

- **Needed for:** which revealed/L1 quantity plays c_t in the anchor.
- **Depends on it:** the cycle term, hence epsilon, hence the whole POLICY slot.
- **Candidates:** `g_minus_trailing_mean` · `credit_gap` · `v`.
- **Trade-off:** DN-1 II.2 says 'the cycle term inherited from L2' but the L2 layer this world emits is a label sequence, not a scalar. Trend growth against its own trailing mean is the closest observable; credit_gap is a genuine cycle measure but a credit one; v is volatility and would make the rule react to markets, which is a different reaction function and arguably a different Committee.

## `voices.fomc.meeting_months`

- **Needed for:** the meeting calendar: which 8 months of each 12 host a decision.
- **Depends on it:** how many POLICY events a quarter contests, and the one-line note that the losing meeting becomes (DN-9 §B.1).
- **Candidates:** `[1, 3, 5, 6, 8, 9, 11, 12]` · `[1, 2, 4, 6, 8, 10, 11, 12]` · `[1, 3, 4, 6, 7, 9, 10, 12]`.
- **Trade-off:** 'meetings_per_year: 8' is set in the skeleton; which months is not, and it decides whether every quarter has two meetings (the third candidate: 2-2-2-2) or whether some quarters have one and the slot contest is uncontested there. The first candidate is the real FOMC's rough shape.

## `voices.fomc.dissent.committee_size`

*Register: A3-B.*

- **Needed for:** how many named members carry hawk-dove priors.
- **Depends on it:** dissent counts, the two-sided-dissent event, the committee scorecard.
- **Candidates:** `8` · `12`.
- **Trade-off:** DN-9 §4.1 says eight to twelve. Fewer members means a dissent is a larger fraction of the vote and reads as more significant; more members means the tails of the prior distribution are populated and one-sided dissents become routine. NOTE THE ROSTER BOUND: `templates/fomc.yaml` ships twelve fictional surnames, so 12 is the largest committee the current bank can seat and a larger one is an editorial job before it is a parameter change. The voice raises rather than reusing a name.

## `voices.fomc.surprise_chip_bp`

- **Needed for:** the |epsilon| cut-point, in basis points, above which the meeting's verdict chip reads SURPRISE rather than IN LINE (DN-9 §D.5).
- **Depends on it:** the verdict-chip distribution panel, and the reader's sense of what counts as a surprise at all.
- **Candidates:** `12.5` · `25.0` · `6.25`.
- **Trade-off:** This was silently riding on `voices.fomc.dissent.threshold` — a different question wearing the same number. Half a step (12.5bp) makes SURPRISE mean 'the rule did not imply this'; a whole step (25bp) reserves it for a decision the rule actively contradicted; a quarter step makes almost every meeting a surprise, which is how a verdict tag stops carrying information.

## `voices.fomc.dissent.prior_spread`

*Register: A3-B.*

- **Needed for:** the standard deviation, in percentage points, of the members' hawk-dove priors drawn at world build.
- **Depends on it:** dissent frequency and whether dissents cluster at turning points.
- **Candidates:** `0.25` · `0.5` · `0.125`.
- **Trade-off:** The spread and the dissent threshold together set the dissent rate; only their ratio matters for frequency, but the spread alone sets how far apart the named hawks and doves are, which is what the copy quotes ('preferred fifty basis points').

## `voices.fomc.dissent.threshold`

- **Needed for:** the distance, in percentage points, between a member's preferred move and the realised one beyond which that member dissents.
- **Depends on it:** dissent counts per meeting; the 'first two-sided dissent in eleven meetings' line.
- **Candidates:** `0.25` · `0.125` · `0.375`.
- **Trade-off:** One full step means a member only dissents when they wanted a different decision, not merely a different emphasis — clean, and it makes dissents rare. Half a step makes them common enough that the two-sided dissent stops being an event, which is the thing DN-9 §4.1 wants it to be.

## `voices.columnists.count`

*Register: A3-B.*

- **Needed for:** how many columnists are cast and quoted per quarter.
- **Depends on it:** the dispersion measure, the end-of-decade scorecard, the repetition panel.
- **Candidates:** `4` · `3` · `5`.
- **Trade-off:** The golden set fixes four by name (Halloran, Vane, Quinones, Ferrers) and the skeleton asks for confirmation rather than assuming it. Three drops one voice from the golden set, which is drift; five needs a fifth register that does not exist yet.

## `voices.columnists.consensus_lag_months`

*Register: A3-B.*

- **Needed for:** how far behind the print the consensus-hugging columnists turn.
- **Depends on it:** the herding mechanic — the reader is meant to notice Halloran turning after the event (golden set §5).
- **Candidates:** `1` · `2` · `3`.
- **Trade-off:** One month makes the turn visible within the same slate and reads as fast; three months makes it visible only across slates, which is more realistic and needs the reader to remember. This is the parameter that decides whether the trap is learnable inside one decade.

## `voices.columnists.dispersion`

*Register: A3-B, N-e.*

- **Needed for:** the model that collapses columnist dispersion when consensus is strong and widens it at turning points (DN-9 §D.11).
- **Depends on it:** the who-thinks-what strip; the divergence signal between the three voices; the mean-dispersion figure on the columnists panel.
- **Candidates:** `severity_band` · `surprise_sd_scaled` · `fixed` · `regime_conditional`.
- **Trade-off:** 'severity_band' is what is BUILT: dispersion is the announcement's severity normalised onto [0,1] by the top of the grammar — a readout of the severity band, not of a surprise in sigma units. It is available on every slot, which is why it is buildable at all. 'surprise_sd_scaled' is the reading DN-9 §D.11 more naturally suggests and is a genuine candidate, but only E02/E03/E04 carry a `surprise_sd`; POLICY carries an epsilon and MARKETS carries neither, so adopting it requires a further decision about what the other slots use. 'regime_conditional' keys off the L2 label and would make dispersion a regime readout — the non-injectivity failure §3.1 warns about. 'fixed' abandons the mechanic. Only the first two of these four are implemented; the others raise.

## `voices.columnists.flows_call_rule`

*Register: A3-B, N-i.*

- **Needed for:** how the flows columnist's directional call is formed, which is what the hit-rate column on the columnists panel scores.
- **Depends on it:** whether the columnist scorecard can distinguish calibration at all.
- **Candidates:** `complement_of_consensus` · `trailing_momentum` · `independent_of_the_print`.
- **Trade-off:** 'complement_of_consensus' is the PLACEHOLDER currently in force and it has a measurement defect that must not become canon: the flows call is the exact negation of the other two, so the three hit rates are always (h, h, 1-h) and the panel cannot tell a well-calibrated cast from a badly calibrated one — it is reporting an identity. 'trailing_momentum' gives flows its own signal (the sign of the trailing window) and lets the three rates move independently; 'independent_of_the_print' draws the call from the bible rather than from the announcement, which is the most faithful to a voice that is supposed to be reading positioning rather than prices, and needs a bible. The panel states the defect while the placeholder is in force.

## `voices.columnists.hit_rate_target`

*Register: A3-B, N-i.*

- **Needed for:** the directional hit rate each columnist is built to achieve.
- **Depends on it:** the final-edition scorecard; the whole 'they must be fallible' condition.
- **Candidates:** `[0.45, 0.6]` · `[0.4, 0.55]` · `[0.5, 0.65]`.
- **Trade-off:** DN-9 §6.1 recommends 45-60% on a one-year horizon. Below 50% the columnists are a contrarian signal and a player learns to fade them, which is a different and worse lesson than learning to discount them; above 60% they become an oracle.

## `voices.economist.stickiness_meetings`

*Register: A3-B, N-t.*

- **Needed for:** the median life of a thesis, in meetings, before capitulation.
- **Depends on it:** the reversal cycle (HOLD/DEFEND/QUALIFY/CAPITULATE) and the strain score.
- **Candidates:** `4` · `6` · `8`.
- **Trade-off:** DN-9 §D.3 recommends calibrating so the median thesis survives 4-6 meetings and the tail survives 10+. Four makes the economist look responsive and, at eight meetings a year, means two theses a year; eight makes the defence phase long enough to be uncomfortable, which is the intended behaviour.

## `voices.economist.confidence_start`

*Register: A3-B, N-t.*

- **Needed for:** the confidence a freshly formed thesis opens at.
- **Depends on it:** how much contradiction is needed before QUALIFY, and the printed confidence figure in the trace.
- **Candidates:** `0.8` · `0.65` · `0.5`.
- **Trade-off:** The golden set shows 0.82 after four confirming months, so the opening value must be below that for recency weighting to be visible. Start high and the voice reads as arrogant; start low and the capitulation floor is reached on noise.

## `voices.economist.confidence_decay_per_contradiction`

*Register: A3-B, N-t.*

- **Needed for:** how much confidence falls per accumulated contradicting event.
- **Depends on it:** thesis life; the DEFEND-to-QUALIFY transition.
- **Candidates:** `0.11` · `0.07` · `0.15`.
- **Trade-off:** This and the floor together determine stickiness, so they must be set with it rather than independently. A large decay makes the agent a weathervane (DN-9 §D.8's named failure mode); a small one makes capitulation never fire inside a decade, which loses the best artifact in Appendix D.

## `voices.economist.capitulation_floor`

*Register: A3-B, N-t.*

- **Needed for:** the confidence below which the thesis is abandoned and named wrong.
- **Depends on it:** the CAPITULATE announcement, which is a first-class event.
- **Candidates:** `0.35` · `0.25` · `0.5`.
- **Trade-off:** DN-9 §D.3 wants capitulation abrupt rather than gradual, which argues for a low floor and a fast fall to it. A high floor produces frequent, undramatic changes of mind — the thing real commentary does and the thing the artifact is designed to make visible instead.

## `voices.economist.risk_book_size`

*Register: A3-B.*

- **Needed for:** how many live concerns the economist carries at any time.
- **Depends on it:** the risk ledger published at the close, and risk-flag parity.
- **Candidates:** `3` · `5` · `4`.
- **Trade-off:** DN-9 §D.14 says three to five. More risks named means a higher absolute count that never materialise, which is the honesty mechanism; it also means the reader has more to remember and the ledger's 'never named' row is harder to earn.

## `voices.economist.risk_materialisation_rate`

*Register: A3-B, N-z.*

- **Needed for:** the fraction of named risks that are allowed to come true.
- **Depends on it:** risk-flag parity (§D.14) — the honesty condition on risk-raising.
- **Candidates:** `0.15` · `0.25` · `0.2`.
- **Trade-off:** DN-9 recommends 15-25%. The load-bearing part is not the rate but that it be INDEPENDENT OF WORLD OUTCOME; the rate itself trades 'reads as thoughtful' against 'reads as an oracle', and at 25% a player who follows every flag is being rewarded too often.

## `voices.economist.filtered_state`

*Register: A3-B, N-s.*

- **Needed for:** the estimator producing s^_t from revealed observables (DN-9 §D.1).
- **Depends on it:** every number the economist quotes about pi*, r* — and the r* revision, which §D.9 calls the best artifact in the appendix.
- **Candidates:** `ewma_on_revealed` · `kalman_on_revealed` · `true_plus_noise`.
- **Trade-off:** DN-9 explicitly recommends a filter over 'true value plus noise', because the noise version gets the error magnitude right and its SERIAL STRUCTURE wrong — and the serial structure is what produces slow realistic revisions instead of jitter. EWMA is the cheap filter: right serial structure, no uncertainty estimate, and one more open constant (its span). A Kalman filter gives the uncertainty and needs a state-space specification that is Quant's to write. The workbench implements EWMA only; the other two raise rather than approximate.

## `voices.economist.filter_span_months`

*Register: A3-B, N-s.*

- **Needed for:** the span, in months, of the EWMA behind the filtered neutral-real-rate estimate r^*.
- **Depends on it:** how fast r^* revises — and therefore whether the r^* revision of DN-9 §D.9 (which the note calls the best artifact in the appendix) happens at all inside a decade.
- **Candidates:** `60` · `24` · `120`.
- **Trade-off:** The span IS the mechanism: it decides whether the estimate 'was 1.4%, now 0.7%' over a year and a half or jitters month to month. A short span makes the economist look responsive and destroys the slow-revision effect; a very long one means the estimate barely moves across a decade and the artifact never fires. This was previously a bare `1/len(series)` in the estimator — an undisclosed tunable that also happened to be world-length-dependent, so the same world narrated at a different horizon filtered differently.

## `voices.economist.strain_weights`

*Register: A3-B, N-v.*

- **Needed for:** the weights in strain_t = f(|eps_narr|, contradiction of s^_t, unmodelled motive invoked, retry count).
- **Depends on it:** the strain panel — which DN-9 §D.6 says is a diagnostic ON THE GENERATOR.
- **Candidates:** `{'epsilon': 1.0, 'contradiction': 1.0, 'unmodelled_motive': 1.0, 'retries': 1.0}` · `{'epsilon': 2.0, 'contradiction': 1.0, 'unmodelled_motive': 1.0, 'retries': 0.5}` · `{'epsilon': 1.0, 'contradiction': 2.0, 'unmodelled_motive': 1.0, 'retries': 0.5}`.
- **Trade-off:** Equal weights make strain a plain count and are the most defensible until someone has looked at a distribution. Weighting epsilon makes strain mostly a restatement of the policy residual and therefore a weaker independent signal; weighting contradiction makes it mostly a statement about the L1 state. Because this metric is proposed for the sealed battery (N-v), the weights should be chosen BEFORE anyone sees the distribution, not after.

## `consensus.persistence_weight`

*Register: A3-B, N-e.*

- **Needed for:** the persistence-weighted street forecast: how much of last month's change is carried into the consensus.
- **Depends on it:** every surprise, therefore every DATA verdict chip and the E02/E03/E04 severities.
- **Candidates:** `0.5` · `0.7` · `1.0`.
- **Trade-off:** 1.0 is naive extrapolation and makes forecasters wrong at every turning point, which is realistic and possibly too realistic; 0.5 damps it. DN-9 §4.2 specifies 'persistence-weighted with a calibrated bias and dispersion' and calibrates none of the three.

## `consensus.bias`

*Register: A3-B, N-e.*

- **Needed for:** the standing bias of the street forecast, in percentage points.
- **Depends on it:** whether surprises are symmetric; the 'forecasters have over-predicted in seven of the last nine months' copy.
- **Candidates:** `0.0` · `-0.05` · `0.05`.
- **Trade-off:** Zero is honest and produces symmetric surprises. A small standing bias is what real consensus does and gives the columnists something to be systematically wrong about — but a bias the player can learn is a free signal, so it must stay small enough that N-2 does not see it.

## `consensus.dispersion`

*Register: A3-B, N-e.*

- **Needed for:** the forecast dispersion, in percentage points, that the surprise is expressed in units of.
- **Depends on it:** every 'surprise_sd' printed on the page; the DATA slot contest.
- **Candidates:** `0.4` · `0.25` · `0.6`.
- **Trade-off:** DN-9 §4.2 asks explicitly whether this is a spec parameter (worlds can be more or less legible) or fixed, and recommends parameterised because 'nobody saw it coming' is a scenario property. Small dispersion inflates every sigma figure; large dispersion makes the 2.3-sigma print of §A.2 impossible.

## `consensus.n_forecasters`

- **Needed for:** the panel size quoted in the consensus copy ('the median of forty-one forecasts').
- **Depends on it:** copy only — no numeric consequence.
- **Candidates:** `41` · `30` · `60`.
- **Trade-off:** Pure furniture, and it is here rather than hardcoded because it is exactly the kind of number that becomes canon by accident. A larger panel makes 'only four of the panel expected an increase' a stronger statement.

## `derived_observables.unemployment.params`

*Register: A3-B, N-b2.*

- **Needed for:** the Okun-type map from trend growth g to an unemployment rate.
- **Depends on it:** E03 entirely; the labour print is DN-9's example of a derived observable and has no series underneath it.
- **Candidates:** `{'u_star': 5.0, 'g_star': 2.5, 'beta': 0.5}` · `{'u_star': 4.5, 'g_star': 2.0, 'beta': 0.4}` · `{'u_star': 5.5, 'g_star': 3.0, 'beta': 0.6}`.
- **Trade-off:** u* and g* set the level the print sits at and beta sets how far it swings. The level is what the reader anchors on and the swing is what makes payrolls day dramatic. DN-9 §3.4 requires these be parameter-fixed at world build, stamped, registered and DISCLOSED — which means they must be someone's decision on the record, not an implementation detail.

## `derived_observables.payrolls_change.params`

*Register: A3-B, N-b2.*

- **Needed for:** the map from the unemployment path to a monthly payrolls change.
- **Depends on it:** E03's headline number (the print a real desk reads first).
- **Candidates:** `{'labour_force_millions': 165.0, 'trend_thousands': 150.0}` · `{'labour_force_millions': 150.0, 'trend_thousands': 100.0}`.
- **Trade-off:** A second derived observable stacked on the first, which compounds the §3.4 warning that 'the temptation to keep deriving is exactly how a display layer quietly becomes a modelling layer'. The alternative is to print unemployment only and drop the payrolls figure.

## `derived_observables.headline_cpi.params`

*Register: A3-B, N-b2.*

- **Needed for:** the window, in months, of the year-on-year CPI transform.
- **Depends on it:** the CPI print, the inflation gap in the anchor, and the adapter's warmup.
- **Candidates:** `{'yoy_window_months': 12}` · `{'yoy_window_months': 6}`.
- **Trade-off:** Twelve months is what 'headline CPI' means and is almost certainly right; it is in the register because §3.4 requires the transform be registered and stamped rather than assumed, and because the window sets how many months of the world have no inflation print at all.

## `derived_observables.growth_print.params`

*Register: A3-B, N-b2.*

- **Needed for:** the quarterly growth print derived from the L1 trend-growth state.
- **Depends on it:** E04, which has no other input.
- **Candidates:** `{'transform': 'identity'}` · `{'transform': 'annualised_qoq'}`.
- **Trade-off:** DN-9 §3.4 recommends the register OPEN WITH THREE ENTRIES (unemployment, payrolls, headline CPI) and that no fourth be added without the same disclosure. E04 needs a fourth. The alternatives are to add it with disclosure or to drop E04 — and dropping it is a real option, since g is already the state everything else is derived from and printing it adds no information.

## `adapter.cpi_yoy_warmup`

- **Needed for:** what the adapter does with the first 12 months, where a year-on-year CPI figure does not yet exist.
- **Depends on it:** whether the first year of the world has inflation prints, an anchor inflation gap, or a POLICY slot at all.
- **Candidates:** `nan_suppress` · `annualise_available` · `require_extra_history`.
- **Trade-off:** 'nan_suppress' is honest — no yoy figure exists, so no print fires and the first four slates run without a DATA inflation item. 'annualise_available' prints a figure from month 2 by annualising what history there is, which is what a real statistical agency would never do. 'require_extra_history' asks the generator for 132 months and narrates the last 120, which is the clean answer and costs a change outside this layer.

## `style.vocabulary_cross_firing`

*Register: A3-B, N-b.*

- **Needed for:** the rate at which regime vocabulary appears OUTSIDE its own regime, per cluster (DN-9 §3.1).
- **Depends on it:** non-injectivity of copy vocabulary onto the L2 label — i.e. the leak gate N-2's vocabulary test.
- **Candidates:** `{'recession': 0.3, 'crisis': 0.2, 'stagflation': 0.25, 'expansion': 0.3}` · `{'recession': 0.15, 'crisis': 0.1, 'stagflation': 0.15, 'expansion': 0.15}` · `{'recession': 0.45, 'crisis': 0.35, 'stagflation': 0.4, 'expansion': 0.45}`.
- **Trade-off:** This is the parameter that decides whether the paper's own vocabulary is a regime readout. Low rates keep the copy natural and leak; high rates break the mapping and make the paper read as evasive or simply wrong, which is its own credibility cost. DN-9 is explicit that a vocabulary BAN does not work because omission is itself a signal, so some positive rate is required.

## `style.layout_states`

*Register: A3-B, N-b.*

- **Needed for:** the map from the six L2 regimes onto the four front-page layout states (DN-9 §5.2).
- **Depends on it:** the deliberately non-injective layout mapping; the SPECIAL band.
- **Candidates:** `{'EXP': 'benign', 'SLOW': 'turning', 'REC': 'stressed', 'CRI': 'dislocated', 'STAG': 'stressed', 'REF': 'benign'}` · `{'EXP': 'benign', 'SLOW': 'benign', 'REC': 'turning', 'CRI': 'dislocated', 'STAG': 'stressed', 'REF': 'turning'}`.
- **Trade-off:** DN-9 §5.2 fixes four layout states against six regimes and says SLOW and REF each share a layout with a neighbour — but does not say which. Every assignment is a claim about which two regimes look alike on the page, and getting it wrong makes the furniture a cleaner regime read than the numbers (the §8 N-2 hazard).

## `diagnostics.columnist_horizon_months`

*Register: A3-B, N-i.*

- **Needed for:** the forward horizon over which a columnist's directional call is scored on the columnists panel.
- **Depends on it:** every hit rate the panel reports, and therefore whether the cast is judged in or out of `voices.columnists.hit_rate_target`.
- **Candidates:** `12` · `6` · `18`.
- **Trade-off:** DN-9 §6.1 sets the hit-rate target on a ONE-YEAR horizon, which argues for 12 — but the horizon and the target band are one decision taken twice, and a cast inside the band at twelve months can be well outside it at six. A short horizon scores the extrapolation the columnists actually make; a long one scores a view they never expressed. It was previously calendar arithmetic (`MONTHS_PER_QUARTER * QUARTERS_PER_YEAR`), which is a threshold wearing a constant's clothes, and it feeds a reported number.

## `diagnostics.repetition_ngram_n`

*Register: A3-B.*

- **Needed for:** n for the repetition panel's n-gram census.
- **Depends on it:** which phrases the panel reports, and therefore whether a thin bank is visible at all.
- **Candidates:** `4` · `3` · `5`.
- **Trade-off:** n=3 catches shared sentence openings and will report template scaffolding that is supposed to repeat; n=5 only fires on near-identical clauses and will miss a bank with two variants. This is a measurement parameter with no effect on copy.

---

*Not investment advice. No firm, person or institution named in the narration layer is real.*
