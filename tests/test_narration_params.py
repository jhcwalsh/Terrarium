"""The open-parameter registry, ``UNRESOLVED.md`` and ``voices.yaml`` are one list.

The workbench's whole value is that it discovered a decision set by building.
That set is only trustworthy if the three places it is written down cannot
drift: the registry that the code raises from, the document a reader reads, and
the config file a run is pointed at.

Catalog-free and checkpoint-free: everything here is repo text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ah.narration.config import UNRESOLVED, ConfigError, load_voices, preflight
from ah.narration.errors import UnresolvedParameter
from ah.narration.params import PARAMETERS, by_key, keys_for, render_unresolved_md

REPO = Path(__file__).resolve().parents[1]
VOICES = REPO / "voices.yaml"
UNRESOLVED_MD = REPO / "src" / "ah" / "narration" / "UNRESOLVED.md"


def test_unresolved_md_is_the_registry_rendered():
    """The document is generated. Edit params.py and regenerate; never both."""
    assert UNRESOLVED_MD.read_text(encoding="utf-8") == render_unresolved_md()


def test_every_unresolved_key_in_voices_yaml_is_described():
    """A key that raises with no entry in UNRESOLVED.md is the failure mode this
    task exists to prevent: an open decision nobody can see."""
    config = load_voices(VOICES)
    described = set(by_key())
    assert set(config.unresolved_keys()) == described


def test_every_registry_entry_has_two_or_more_candidates():
    """'2-3 candidate values with the trade-off between them' is the contract.
    One candidate is a recommendation wearing a registry entry's clothes."""
    for param in PARAMETERS:
        assert len(param.candidates) >= 2, param.key
        assert len(set(map(repr, param.candidates))) == len(param.candidates), param.key
        assert param.needed_for and param.depends_on and param.trade_off, param.key


def test_no_registry_entry_is_resolved_in_the_shipped_config():
    """The shipped voices.yaml must ship 100% open. If a future change resolves
    one, it must be removed from the registry in the same commit."""
    config = load_voices(VOICES)
    for param in PARAMETERS:
        assert config.is_unresolved(param.key), f"{param.key} is no longer UNRESOLVED"


def test_preflight_fails_with_the_whole_list_not_the_first_key():
    config = load_voices(VOICES)
    with pytest.raises(UnresolvedParameter) as excinfo:
        preflight(config, book_available=False)
    keys = excinfo.value.keys
    assert set(keys) == set(keys_for(book_available=False))
    assert len(keys) > 1
    assert "UNRESOLVED.md" in str(excinfo.value)


def test_book_gated_parameters_are_excluded_when_the_book_is_absent():
    """A world with no book must fail on what it would actually have read."""
    without = set(keys_for(book_available=False))
    with_book = set(keys_for(book_available=True))
    assert without < with_book
    assert "events.E18.threshold" in with_book - without


def test_get_has_no_default_and_raises_on_the_sentinel(tmp_path: Path):
    path = tmp_path / "v.yaml"
    path.write_text(
        "events: {E01: {kind: point, threshold: UNRESOLVED}}\nslate: {min_slots: 3}\n",
        encoding="utf-8",
    )
    config = load_voices(path)
    assert config.get("slate.min_slots") == 3
    with pytest.raises(UnresolvedParameter):
        config.get("events.E01.threshold")
    with pytest.raises(ConfigError):
        config.get("slate.nonexistent")


def test_kind_is_structural_not_configurable(tmp_path: Path):
    """DN-9 §3.2: a state class firing every period is a defect, not a config."""
    path = tmp_path / "v.yaml"
    path.write_text("events: {E10: {kind: point, milestones: UNRESOLVED}}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="structural"):
        load_voices(path)


def test_config_hash_moves_when_one_value_moves(tmp_path: Path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("events: {E01: {kind: point, threshold: 0.18}}\n", encoding="utf-8")
    b.write_text("events: {E01: {kind: point, threshold: 0.25}}\n", encoding="utf-8")
    assert load_voices(a).hash() != load_voices(b).hash()
    assert load_voices(a).hash() == load_voices(a).hash()


def test_the_sentinel_is_a_string_so_it_survives_a_yaml_round_trip():
    assert isinstance(UNRESOLVED, str)
