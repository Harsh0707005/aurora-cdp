"""Aurora CDP: a local-first customer data platform modelled on Amperity's documented behaviours.

Package map (see docs/architecture.md for the mapping to Amperity concepts):

- ingestion     feeds -> bronze landing zone -> semantic tagging -> normalisation (Unified Preprocessed Raw)
- storage       DuckDB connection + versioned DDL (bronze / silver / gold, CDC + id ledger)
- stitch        blocking -> features -> scoring -> conflict-aware clustering -> stable ID assignment
- profile       survivorship -> merged customers / customer 360 / profile events
- audiences     segments + destinations (CSV, webhook stub)
- orchestration YAML pipeline DAG + minimal scheduler
- api           FastAPI + Jinja2 identity dashboard
"""

__version__ = "0.1.0"
