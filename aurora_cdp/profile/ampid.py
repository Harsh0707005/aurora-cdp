"""AmpID compatibility mode (Amperity-style external ids).

* ``identity.external_id_name`` (default ``amperity_id``): every export that carries ``unified_id`` /
  ``aurora_id`` also carries the external column with the same value, and previous-assignment inputs may use it
  instead of ``unified_id``. The stable id itself is unchanged, so downstream systems built against Amperity's
  column name keep working.
* ``identity.email_ampid_assignment``: ``gold_email_ampid`` narrows the many-to-many e-mail ↔ customer relation
  to exactly one customer per e-mail (``most_records``: the customer with the most records carrying it; ties →
  most recent record), kept as SCD2 so re-assignments are visible.
"""

from __future__ import annotations

from datetime import datetime

import duckdb

from aurora_cdp.config import Config


def external_id_name(cfg: Config) -> str:
    return str((cfg.get("identity") or {}).get("external_id_name") or "amperity_id")


def with_external_id(df, cfg: Config, source_col: str = "unified_id"):
    """Add the external id column (same value as the stable id) when enabled; no-op otherwise."""
    ident = cfg.get("identity") or {}
    if not ident.get("ampid_mode", True) or source_col not in df.columns:
        return df
    name = external_id_name(cfg)
    if name not in df.columns:
        df = df.copy()
        df[name] = df[source_col]
    return df


def assign_email_ampids(con: duckdb.DuckDBPyConnection, cfg: Config, run_id: str) -> dict:
    """Narrow e-mail -> customer to 1:1 for the clusters of ``run_id`` (SCD2 rows in gold_email_ampid)."""
    now = datetime.utcnow()
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _email_cand AS
        SELECT s.email_norm AS email, c.aurora_id, COUNT(*) AS n, MAX(COALESCE(s.update_dt, TIMESTAMP '1970-01-01')) AS last_dt
        FROM stitch_clusters c
        JOIN (
            SELECT * FROM silver_unified_preprocessed
            QUALIFY ROW_NUMBER() OVER (PARTITION BY datasource, pk ORDER BY preprocessed_at DESC) = 1
        ) s ON s.datasource = c.datasource AND s.pk = c.pk
        WHERE c.run_id = ? AND s.email_norm IS NOT NULL
        GROUP BY 1, 2
        """,
        [run_id],
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _email_pick AS
        SELECT email, aurora_id, candidates,
               CASE WHEN candidates = 1 THEN 'unique' WHEN rn_records = 1 AND ties = 1 THEN 'most_records' ELSE 'most_recent' END AS rule
        FROM (
            SELECT email, aurora_id,
                   COUNT(*) OVER (PARTITION BY email) AS candidates,
                   ROW_NUMBER() OVER (PARTITION BY email ORDER BY n DESC, last_dt DESC, aurora_id) AS rn,
                   ROW_NUMBER() OVER (PARTITION BY email ORDER BY n DESC, aurora_id) AS rn_records,
                   SUM(CASE WHEN n = max_n THEN 1 ELSE 0 END) OVER (PARTITION BY email) AS ties
            FROM (SELECT *, MAX(n) OVER (PARTITION BY email) AS max_n FROM _email_cand)
        ) WHERE rn = 1
        """
    )
    changed = con.execute(
        """
        SELECT COUNT(*) FROM _email_pick p LEFT JOIN gold_email_ampid g ON g.is_current AND g.email = p.email
        WHERE g.email IS NULL OR g.aurora_id <> p.aurora_id
        """
    ).fetchone()[0]
    con.execute(
        """
        UPDATE gold_email_ampid SET valid_to = ?, is_current = FALSE
        WHERE is_current AND email IN (
            SELECT p.email FROM _email_pick p LEFT JOIN gold_email_ampid g ON g.is_current AND g.email = p.email
            WHERE g.email IS NULL OR g.aurora_id <> p.aurora_id
            UNION SELECT email FROM gold_email_ampid WHERE is_current AND email NOT IN (SELECT email FROM _email_pick)
        )
        """,
        [now],
    )
    con.execute(
        """
        INSERT INTO gold_email_ampid
        SELECT p.email, p.aurora_id, p.candidates, p.rule, ?, ?, NULL, TRUE
        FROM _email_pick p WHERE NOT EXISTS (SELECT 1 FROM gold_email_ampid g WHERE g.is_current AND g.email = p.email AND g.aurora_id = p.aurora_id)
        """,
        [run_id, now],
    )
    total, narrowed = con.execute("SELECT COUNT(*), SUM(CASE WHEN candidates > 1 THEN 1 ELSE 0 END) FROM _email_pick").fetchone()
    con.execute("DROP TABLE IF EXISTS _email_cand"); con.execute("DROP TABLE IF EXISTS _email_pick")
    return {"emails": int(total or 0), "emails_narrowed": int(narrowed or 0), "email_ampid_changed": int(changed)}
