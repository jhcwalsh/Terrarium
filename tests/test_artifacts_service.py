"""WP4.1 — the artifact service: calendar, chronicle record, renderers.

The boundary is the first test: the certified numeric path never imports
the artifact layer. Then: the calendar rides the schema's x_ escape hatch
and schedules deterministically; the G9 record refuses incompleteness and
inherits the chronicle's append-only triggers; every renderer marks its
output and export re-applies the marking.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, ClassVar

import jsonschema
import pytest

from ah.artifacts import calendar as cal
from ah.artifacts import chronicle as pub
from ah.artifacts import render
from ah.store.db import connect

ROOT = Path(__file__).resolve().parents[1]

CALENDAR_BLOCK = {
    "x_temporal_delivery": {
        "artifact_calendar": [
            {"artifact_type": "wire_item", "cadence": "monthly", "author_tier": 1},
            {"artifact_type": "release_page", "cadence": "monthly", "author_tier": 1},
            {"artifact_type": "statement", "cadence": "quarterly", "author_tier": 1},
            {
                "artifact_type": "board_pack",
                "cadence": "quarterly",
                "author_tier": 1,
                "offset_weeks": -2,
            },
            {"artifact_type": "letterhead", "cadence": "event", "author_tier": 2},
        ]
    }
}


class TestBoundary:
    def test_numeric_path_never_imports_artifacts(self):
        """The leakage-guard discipline, pointed at the storytellers."""
        for tree in ("core", "gen", "port"):
            for path in (ROOT / "src" / "ah" / tree).rglob("*.py"):
                source = path.read_text(encoding="utf-8")
                assert "ah.artifacts" not in source and "from ah import artifacts" not in source, (
                    f"{path} imports the artifact layer across the boundary"
                )


class TestCalendar:
    def _spec(self) -> dict:
        doc = json.loads(
            (ROOT / "schemas" / "example-long-stagflation.worldspec.json").read_text("utf-8")
        )
        doc["extensions"] = {**doc.get("extensions", {}), **CALENDAR_BLOCK}
        return doc

    def test_calendar_block_is_schema_valid(self):
        major_minor = ".".join(self._spec()["spec_version"].split(".")[:2])
        schema = json.loads(
            (ROOT / "schemas" / f"worldspec-v{major_minor}.schema.json").read_text("utf-8")
        )
        jsonschema.Draft202012Validator(schema).validate(self._spec())

    def test_reads_declared_entries_and_absent_block_is_empty(self):
        entries = cal.read_calendar(self._spec())
        assert len(entries) == 5
        assert cal.read_calendar({"world_id": "w"}) == []

    def test_malformed_block_raises(self):
        with pytest.raises(cal.CalendarError, match="artifact_calendar"):
            cal.read_calendar({"extensions": {"x_temporal_delivery": {"oops": []}}})
        with pytest.raises(cal.CalendarError, match="unknown calendar entry keys"):
            cal.read_calendar(
                {
                    "extensions": {
                        "x_temporal_delivery": {
                            "artifact_calendar": [
                                {
                                    "artifact_type": "wire_item",
                                    "cadence": "monthly",
                                    "author_tier": 1,
                                    "surprise": True,
                                }
                            ]
                        }
                    }
                }
            )
        with pytest.raises(cal.CalendarError, match="unknown artifact_type"):
            cal.CalendarEntry("tweet", "monthly", 1)
        with pytest.raises(cal.CalendarError, match="cadence"):
            cal.CalendarEntry("wire_item", "daily", 1)
        with pytest.raises(cal.CalendarError, match="author_tier"):
            cal.CalendarEntry("wire_item", "monthly", 3)

    def test_schedule_is_deterministic_and_quarterly_lands_quarter_end(self):
        entries = cal.read_calendar(self._spec())
        a = cal.schedule(entries, 12)
        b = cal.schedule(list(reversed(entries)), 12)
        assert a == b  # declaration order never changes the schedule
        months_stmt = [s.month for s in a if s.artifact_type == "statement"]
        assert months_stmt == [2, 5, 8, 11]
        assert all(s.artifact_type != "letterhead" for s in a)  # event: runtime-only
        pack = next(s for s in a if s.artifact_type == "board_pack")
        assert pack.week == -2  # T-2 world-weeks before the decision window
        assert len([s for s in a if s.artifact_type == "wire_item"]) == 12


class TestPublicationRecord:
    def _conn(self) -> sqlite3.Connection:
        return connect(":memory:")

    def _record(self, conn, **overrides):
        kwargs: dict[str, Any] = dict(
            world_id="w1",
            seq=1,
            created_at="2026-08-02T00:00:00+00:00",
            artifact_type="wire_item",
            dateline="2028-03-15",
            author_tier=1,
            gate_result="tier1_deterministic",
            payload_hash="sha256:" + "0" * 64,
        )
        kwargs.update(overrides)
        return pub.record_publication(conn, **kwargs)

    def test_round_trips_the_g9_record(self):
        conn = self._conn()
        self._record(conn)
        rows = pub.read_publications(conn, "w1")
        assert len(rows) == 1
        p = rows[0]["payload"]
        assert p["artifact_type"] == "wire_item" and p["gate_result"] == "tier1_deterministic"
        assert p["payload_hash"].startswith("sha256:")

    def test_incomplete_records_refuse(self):
        conn = self._conn()
        with pytest.raises(pub.PublicationError, match="payload_hash"):
            self._record(conn, payload_hash="md5:nope")
        with pytest.raises(pub.PublicationError, match="dateline"):
            self._record(conn, dateline="")
        with pytest.raises(pub.PublicationError, match="gate_result"):
            self._record(conn, gate_result="shrug")
        with pytest.raises(pub.PublicationError, match="tier-2"):
            self._record(conn, author_tier=2, gate_result="pass")  # no prompt/model

    def test_tier2_with_provenance_publishes(self):
        conn = self._conn()
        self._record(
            conn,
            author_tier=2,
            gate_result="pass",
            prompt_version="author-prompt/letter@1.0",
            model_id="claude-fable-5",
            retry_count=1,
        )
        p = pub.read_publications(conn, "w1")[0]["payload"]
        assert p["prompt_version"] == "author-prompt/letter@1.0"
        assert p["retry_count"] == 1

    def test_publications_inherit_append_only(self):
        conn = self._conn()
        row_id = self._record(conn)
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("UPDATE chronicle SET payload='{}' WHERE id=?", (row_id,))
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("DELETE FROM chronicle WHERE id=?", (row_id,))


class TestRenderers:
    PAYLOADS: ClassVar[dict[str, dict]] = {
        "wire_item": {
            "world_id": "w1",
            "dateline": "2028-03-15",
            "headline": "Spreads widen",
            "body": "High-yield spreads moved 40bps.",
        },
        "release_page": {
            "world_id": "w1",
            "dateline": "2028-03-15",
            "release_name": "CPI, February",
            "rows": [{"series": "cpi_yoy", "value": "3.1%", "prior": "3.4%", "revision": ""}],
        },
        "statement": {
            "world_id": "w1",
            "dateline": "2028-03-31",
            "title": "Quarterly Statement",
            "lines": ["Total value: 1,204.5", "Net flow: -12.0"],
        },
        "letterhead": {
            "world_id": "w1",
            "dateline": "2028-04-15",
            "entity_name": "Meridian Crest Partners",
            "body": "(gated body)",
        },
        "board_pack": {
            "world_id": "w1",
            "dateline": "2028-05-01",
            "sections": [{"title": "Performance", "lines": ["Q1 net: +1.2%"]}],
        },
    }

    def test_every_type_renders_with_the_watermark(self):
        for artifact_type, payload in self.PAYLOADS.items():
            text = render.render(artifact_type, payload)
            assert render.WATERMARK_BANNER in text, artifact_type
            assert render.WATERMARK_FOOTER in text, artifact_type
            assert payload["dateline"] in text

    def test_missing_payload_fields_refuse(self):
        with pytest.raises(render.RenderError, match="missing"):
            render.render("wire_item", {"world_id": "w1", "dateline": "d"})
        with pytest.raises(render.RenderError, match="no renderer"):
            render.render("tweet", {})

    def test_export_reapplies_marking_and_is_idempotent(self):
        text = render.render("wire_item", self.PAYLOADS["wire_item"])
        assert render.export(text) == text  # already marked: unchanged
        stripped = text.replace(render.WATERMARK_BANNER + "\n", "").replace(
            "\n" + render.WATERMARK_FOOTER, ""
        )
        again = render.export(stripped)
        assert render.WATERMARK_BANNER in again and render.WATERMARK_FOOTER in again

    def test_payload_hash_ignores_key_order(self):
        a = {"x": 1, "y": {"b": 2, "a": 3}}
        b = {"y": {"a": 3, "b": 2}, "x": 1}
        assert render.payload_hash(a) == render.payload_hash(b)
        assert render.payload_hash(a).startswith("sha256:")
