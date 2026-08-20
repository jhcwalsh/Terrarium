"""The retired-world fence — the platform's single list of world ids that are
records of earlier releases: readable forever, never re-runnable, never
selectable for new play.

Lives in its own module (chosen-PE release fix round, 2026-08-20) because TWO
surfaces must read one fence: ``ah.cli`` refuses to rebuild these worlds, and
``ah.serve``'s ``/worlds`` now marks them ``"retired": true`` so the app's
picker can hide them (server-authoritative — the app never keeps its own list
of retired GENERATED worlds; ``HIDDEN_WORLD_IDS`` in the app remains only for
702's superseded-methodology case, which predates this fence). Importing
``ah.cli`` from ``ah.serve`` would drag the whole Typer CLI (and its data/exp
sub-apps) into the service process, so the frozenset moved here and ``ah.cli``
re-exports it.

ER-14 close-out (D-ER14-2, 2026-08-18). These worlds' numbers - and, with the
infrastructure sleeve, the SHAPE of their tapes - changed under toy-v0.7, but
their ids are records of what a campaign actually executed. Renumbering would
not reproduce those campaigns, only produce differently-shaped new ones under
new ids; leaving them runnable would invite exactly the leaderboard collision
the fences exist to prevent. So: readable forever, never re-runnable.
Chosen-PE adoption (D-ER16-1/AM-2026-08-19-001, 2026-08-19): the same rule,
second application. 711/712/713 AND 604 consumed the v1.2 sleeve-mappings
equation; the platform now translates the identical declared scenarios
through v1.3 (pm_buyout chosen coefficients), so every generated-plane
world id retires and the 72x successors replace them - scores under
port-v5-inflation-gen and port-v6-chosen-pe-gen must never share a
leaderboard row.
"""

from __future__ import annotations

RETIRED_WORLD_IDS = frozenset(
    {
        "00000000-0000-4000-9000-000000000701",  # stress_1974
        "00000000-0000-4000-9000-000000000703",  # stress_1990
        "00000000-0000-4000-9000-000000000801",  # narration_1974
        "00000000-0000-4000-9000-000000000802",  # spine_pilot
        "00000000-0000-4000-9000-000000000711",  # stress_1974_successor pre-chosen-PE
        "00000000-0000-4000-9000-000000000712",  # gulf_decade pre-chosen-PE
        "00000000-0000-4000-9000-000000000713",  # stress_1990_successor pre-chosen-PE
        "00000000-0000-4000-9000-000000000604",  # stagflation_1974 pre-chosen-PE
    }
)
