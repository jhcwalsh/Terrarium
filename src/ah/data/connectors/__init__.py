"""Source connectors: one per public data source (STEP1-DATA-PLAN §WP1.2).

Each connector implements the :class:`~ah.data.connectors.base.Connector` protocol:
``fetch()`` performs the (retrying, rate-limited) network download and ``parse()``
turns the raw artifact into a canonical ``(date, value)`` frame. ``fetch()`` is never
exercised in tests (pytest-socket blocks the network); ``parse()`` is covered by
golden tests over recorded/synthetic fixtures.
"""
