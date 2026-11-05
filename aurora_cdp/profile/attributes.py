"""Customer Attributes (Amperity: the Customer Attributes table family, internals §4.2): behavioural features
computed per id from the profile event timeline — first / second / latest order, lifetime and L12M / L6M / L3M /
L30D rollups by brand, channel and store, one-and-done, single/multi brand & channel, early repeat, RFM.

Definitions are the ones the Williams-Sonoma CUSTOMER contract carries (tools/wsi_edap_sim.expected_customer is the
executable reference): preferred brand / channel / store = the one with the highest net amount (ties: alphabetical),
*_brands / *_channels / *_stores = comma-joined sorted distinct values, frequency = orders, AOV = net / orders,
average item price = net / items, early repeat = second order within 90 days, RFM over the last 12 months with
recency buckets 30/90/180/270 days, frequency = min(orders, 5), monetary 150/400/1000/2000.

Event fields come from the ``events[].attributes`` mapping onto the event payload (raw feed columns):
    events:
      - source: oms
        feed: orders
        fk_column: CUSTOMER_ID
        fk_namespace: oms
        event_type: order
        ts_column: ORDER_DT
        amount_column: NET_AMT
        attributes: {order_id: ORDER_ID, brand: CONCEPT_CD, channel: SUB_CHANNEL_TYPE_CD, store: LOCATION_ID,
                     total: GROSS_AMT, items: TOTAL_ITEMS}
"""

from __future__ import annotations

import logging
from datetime import datetime

import duckdb

from aurora_cdp.config import Config
from aurora_cdp.storage.duck import latest_run_id

log = logging.getLogger(__name__)

WINDOWS = {"l12m": 365, "l6m": 182, "l3m": 91, "l30d": 30}
ATTR_KEYS = ("order_id", "brand", "channel", "store", "total", "items")


def _payload_expr(attrs: dict, key: str, cast: str = "VARCHAR") -> str:
    col = attrs.get(key)
    return f"TRY_CAST(json_extract_string(payload, '$.{col}') AS {cast})" if col else "NULL"


def _window_sql(prefix: str, since_expr: str) -> str:
    """Per-id aggregates over orders with order_date >= since (``since_expr`` may be '1900-01-01' for lifetime)."""
    return f"""
    {prefix} AS (
      SELECT aurora_id,
             string_agg(DISTINCT brand, ',' ORDER BY brand) AS {prefix}_brands,
             arg_max(brand, net_by_brand) FILTER (WHERE brand IS NOT NULL) AS {prefix}_preferred_brand,
             string_agg(DISTINCT channel, ',' ORDER BY channel) AS {prefix}_channels,
             arg_max(channel, net_by_channel) FILTER (WHERE channel IS NOT NULL) AS {prefix}_preferred_channel,
             string_agg(DISTINCT store, ',' ORDER BY store) AS {prefix}_stores,
             arg_max(store, net_by_store) FILTER (WHERE store IS NOT NULL) AS {prefix}_preferred_store_id,
             ROUND(SUM(net), 2) AS {prefix}_order_net_amt,
             ROUND(SUM(total), 2) AS {prefix}_order_total_amt,
             COUNT(*) AS {prefix}_order_frequency,
             SUM(items) AS {prefix}_{'order_' if prefix == 'lifetime' else ''}total_items,
             ROUND(SUM(net) / COUNT(*), 2) AS {prefix}_average_order_value_amt,
             CASE WHEN SUM(items) > 0 THEN ROUND(SUM(net) / SUM(items), 2) ELSE 0.0 END AS {prefix}_average_item_price,
             CAST(ROUND(SUM(items) * 1.0 / COUNT(*)) AS BIGINT) AS {prefix}_average_num_items
      FROM (
        SELECT o.*,
               SUM(net) OVER (PARTITION BY aurora_id, brand) AS net_by_brand,
               SUM(net) OVER (PARTITION BY aurora_id, channel) AS net_by_channel,
               SUM(net) OVER (PARTITION BY aurora_id, store) AS net_by_store
        FROM _orders o WHERE order_date >= {since_expr}
      ) GROUP BY aurora_id
    )"""


def build_customer_attributes(con: duckdb.DuckDBPyConnection, cfg: Config, run_id: str | None = None, as_of: str | None = None) -> int:
    """Rebuild ``customer_attributes`` for the current ids from ``gold_profile_events`` (event_type order)."""
    run_id = run_id or latest_run_id(con)
    specs = [s for s in (cfg.get("events") or []) if s.get("event_type", "event") == "order"]
    attrs: dict = {}
    for s in specs:  # one mapping is enough for the whole timeline; the first spec with attributes wins per key
        for k, v in (s.get("attributes") or {}).items():
            attrs.setdefault(k, v)
    con.execute("DELETE FROM customer_attributes")
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE _orders AS
        SELECT aurora_id, CAST(event_ts AS DATE) AS order_date, event_ts, COALESCE(amount, 0.0) AS net,
               COALESCE({_payload_expr(attrs, "total", "DOUBLE")}, amount, 0.0) AS total,
               COALESCE({_payload_expr(attrs, "items", "BIGINT")}, 0) AS items,
               COALESCE({_payload_expr(attrs, "order_id")}, event_id) AS order_id,
               {_payload_expr(attrs, "brand")} AS brand, {_payload_expr(attrs, "channel")} AS channel, {_payload_expr(attrs, "store")} AS store
        FROM gold_profile_events WHERE event_type = 'order' AND aurora_id IS NOT NULL AND event_ts IS NOT NULL
        """)
    if con.execute("SELECT COUNT(*) FROM _orders").fetchone()[0] == 0:
        return 0
    as_of_expr = f"DATE '{as_of}'" if as_of else "(SELECT MAX(order_date) FROM _orders)"
    con.execute(f"CREATE OR REPLACE TEMP TABLE _asof AS SELECT {as_of_expr} AS d")
    windows = ",".join(_window_sql(p, f"(SELECT d - INTERVAL {days} DAY FROM _asof)") for p, days in WINDOWS.items())
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE _attrs AS
        WITH ranked AS (
          SELECT *, ROW_NUMBER() OVER (PARTITION BY aurora_id ORDER BY order_date, order_id) AS rn,
                 ROW_NUMBER() OVER (PARTITION BY aurora_id ORDER BY order_date DESC, order_id DESC) AS rn_desc
          FROM _orders
        ), f AS (SELECT * FROM ranked WHERE rn = 1), s AS (SELECT * FROM ranked WHERE rn = 2), l AS (SELECT * FROM ranked WHERE rn_desc = 1),
        {_window_sql("lifetime", "DATE '1900-01-01'")},
        {windows},
        flags AS (
          SELECT aurora_id, COUNT(*) AS n, COUNT(DISTINCT brand) AS nb, COUNT(DISTINCT channel) AS nc,
                 MAX(net) AS largest, MAX(CASE WHEN channel = 'RETAIL' THEN 1 ELSE 0 END) AS retail
          FROM _orders GROUP BY aurora_id
        ), rfm AS (
          SELECT aurora_id,
                 CASE WHEN rec <= 30 THEN 5 WHEN rec <= 90 THEN 4 WHEN rec <= 180 THEN 3 WHEN rec <= 270 THEN 2 ELSE 1 END AS r,
                 LEAST(n12, 5) AS f,
                 CASE WHEN m >= 2000 THEN 5 WHEN m >= 1000 THEN 4 WHEN m >= 400 THEN 3 WHEN m >= 150 THEN 2 ELSE 1 END AS m
          FROM (SELECT aurora_id, date_diff('day', MAX(order_date), (SELECT d FROM _asof)) AS rec, COUNT(*) AS n12, SUM(net) AS m
                FROM _orders WHERE order_date >= (SELECT d - INTERVAL 365 DAY FROM _asof) GROUP BY aurora_id)
        )
        SELECT f.aurora_id, (SELECT d FROM _asof) AS as_of,
               f.brand AS first_order_brand, f.channel AS first_order_channel, f.store AS first_order_store_id, f.order_id AS first_order_id,
               f.order_date AS first_order_date, f.net AS first_order_net_amt, f.total AS first_order_total_amt, f.items AS first_order_total_items,
               s.brand AS second_order_brand, s.channel AS second_order_channel, s.store AS second_order_store_id, s.order_id AS second_order_id,
               s.order_date AS second_order_date, s.net AS second_order_net_amt, s.total AS second_order_total_amt, s.items AS second_order_total_items,
               l.brand AS latest_order_brand, l.channel AS latest_order_channel, l.store AS latest_order_store_id, l.order_id AS latest_order_id,
               l.order_date AS latest_order_date, l.net AS latest_order_net_amt, l.total AS latest_order_total_amt, l.items AS latest_order_total_items,
               date_diff('day', f.order_date, s.order_date) AS first_to_second_order_days,
               date_diff('day', f.order_date, l.order_date) AS first_to_latest_order_days,
               date_diff('day', l.order_date, (SELECT d FROM _asof)) AS days_since_latest_order,
               CASE WHEN fl.n = 1 THEN 'Y' ELSE 'N' END AS one_and_done,
               CASE WHEN fl.nb = 1 THEN 'Y' ELSE 'N' END AS single_brand, CASE WHEN fl.nb = 1 THEN 'N' ELSE 'Y' END AS multi_brand,
               CASE WHEN fl.nc = 1 THEN 'Y' ELSE 'N' END AS single_channel, CASE WHEN fl.nc = 1 THEN 'N' ELSE 'Y' END AS multi_channel,
               CASE WHEN s.order_date IS NOT NULL AND date_diff('day', f.order_date, s.order_date) <= 90 THEN 'Y' ELSE 'N' END AS early_repeat_purchaser,
               CASE WHEN fl.retail = 1 THEN 'Y' ELSE 'N' END AS retail_flag,
               lifetime.* EXCLUDE (aurora_id), fl.largest AS lifetime_largest_order_value_amt,
               l12m.* EXCLUDE (aurora_id), l6m.* EXCLUDE (aurora_id), l3m.* EXCLUDE (aurora_id), l30d.* EXCLUDE (aurora_id),
               CAST(rfm.r AS VARCHAR) AS l12m_recency, CAST(rfm.f AS VARCHAR) AS l12m_frequency, CAST(rfm.m AS VARCHAR) AS l12m_monetary,
               rfm.r * 100 + rfm.f * 10 + rfm.m AS l12m_rfm_score,
               CASE WHEN rfm.r IS NULL THEN 'LAPSED' WHEN rfm.r >= 4 AND rfm.f >= 3 AND rfm.m >= 4 THEN 'CHAMPION' WHEN rfm.f >= 3 THEN 'LOYAL'
                    WHEN rfm.r >= 4 THEN 'RECENT' WHEN rfm.r <= 2 AND rfm.f >= 2 THEN 'AT_RISK' ELSE 'OCCASIONAL' END AS l12m_rfm_customer_segment
        FROM f LEFT JOIN s USING (aurora_id) JOIN l USING (aurora_id) JOIN flags fl USING (aurora_id) JOIN lifetime USING (aurora_id)
        LEFT JOIN l12m USING (aurora_id) LEFT JOIN l6m USING (aurora_id) LEFT JOIN l3m USING (aurora_id) LEFT JOIN l30d USING (aurora_id)
        LEFT JOIN rfm USING (aurora_id)
        """)
    cols = [r[1] for r in con.execute("PRAGMA table_info('customer_attributes')").fetchall()]
    have = {r[1] for r in con.execute("PRAGMA table_info('_attrs')").fetchall()}
    select = ", ".join(c if c in have else ("?" if c in ("run_id", "built_at") else "NULL") for c in cols)
    con.execute(f"INSERT INTO customer_attributes ({', '.join(cols)}) SELECT {select} FROM _attrs", [run_id, datetime.utcnow()])
    n = con.execute("SELECT COUNT(*) FROM customer_attributes").fetchone()[0]
    for t in ("_orders", "_asof", "_attrs"):
        con.execute(f"DROP TABLE IF EXISTS {t}")
    log.info("customer attributes built for %d ids", n)
    return int(n)
