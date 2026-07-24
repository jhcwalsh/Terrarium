"""Scenario compiler interface + offline fixture harness.

The Anthropic adapter performs live calls only via an explicit CLI flag and is
never imported by tests (pytest-socket enforces the no-network rule).
"""
