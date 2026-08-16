"""The two ways a narration build is allowed to fail loudly.

Both exist to stop the same thing: a number entering the corpus without anyone
having decided it. :class:`UnresolvedParameter` refuses a value;
:class:`MissingSeriesError` refuses an input. Neither has a fallback path.
"""

from __future__ import annotations


class NarrationError(RuntimeError):
    """Base for every narration-layer failure."""


class UnresolvedParameter(NarrationError):
    """A parameter the build needs that ``voices.yaml`` does not resolve.

    Carries **every** unresolved key the build would have needed, not just the
    first one hit — the task's rule is that a run fails with *the list*, so one
    build surfaces the whole decision set rather than one key per re-run.
    """

    def __init__(self, keys: list[str], *, config_path: str, unresolved_doc: str) -> None:
        self.keys = list(keys)
        self.config_path = config_path
        self.unresolved_doc = unresolved_doc
        lines = [
            f"{len(self.keys)} parameter(s) the build needs are UNRESOLVED in {config_path}.",
            "No default is substituted and the run does not proceed.",
            "",
        ]
        lines += [f"  - {key}" for key in self.keys]
        lines += ["", f"Each is described, with candidate values, in {unresolved_doc}"]
        super().__init__("\n".join(lines))


class MissingSeriesError(NarrationError):
    """A required input series the generated world does not carry.

    Names the series (and, where the series is derived, the generator factor it
    would have been derived from). It is never synthesised.
    """

    def __init__(self, series: str, *, detail: str) -> None:
        self.series = series
        super().__init__(f"required series '{series}' is not available: {detail}")
