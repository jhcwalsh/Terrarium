"""Data layer (Step 1): sourcing, vintage storage, QC, splicing, derivation.

pandas is permitted throughout this package (unlike ``ah.core``). Storage is
immutable-vintage Parquet plus a DuckDB catalog; the Step-0 SQLite stores remain
for RunRecords/chronicle only.
"""
