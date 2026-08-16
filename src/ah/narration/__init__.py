"""The narration workbench (TASK-wp4.2, DN-9 "The Wire").

**This package is a DISPLAY surface.** It reads the realised path and renders
copy; nothing numeric depends on it. The repo's narrative-blindness invariant is
preserved by direction: ``ah.narration`` may import from ``ah.core``/``ah.gen``,
and nothing in ``ah.core``/``ah.gen``/``ah.eval``/``ah.port`` may import from
here. ``tests/test_narration_boundary.py`` asserts that direction.

**Nothing tunable is decided here.** Every tunable value is read from
``voices.yaml``. A key whose value is the sentinel ``UNRESOLVED`` raises
:class:`~ah.narration.errors.UnresolvedParameter` and the run fails with the
full list — it never proceeds on a default. The open list is
``src/ah/narration/UNRESOLVED.md``, generated from :mod:`ah.narration.params`
and machine-checked against it.

The workbench loop::

    python -m ah.narration build --world <preset path or name> --voices voices.yaml --out runs/<id>
    python -m ah.narration compare runs/<a> runs/<b>
"""

from __future__ import annotations

#: Stamped in every manifest. Bump when the event grammar or the slate
#: assembly changes shape (not when copy or config values change).
NARRATION_VERSION = "0.1.0"

#: Stamped in every manifest. Bump when the generator -> input-contract mapping
#: in ``adapters/world.py`` changes, because every downstream number moves.
ADAPTER_VERSION = "0.1.0"

__all__ = ["ADAPTER_VERSION", "NARRATION_VERSION"]
