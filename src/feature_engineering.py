from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .config import PipelineConfig
from .utils import safe_divide, write_json


EVENT_TABLES = {
    "product_buy": ["client_id", "timestamp", "sku"],
    "add_to_cart": ["client_id", "timestamp", "sku"],
    "remove_from_cart": ["client_id", "timestamp", "sku"],
    "page_visit": ["client_id", "timestamp", "url"],
    "search_query": ["client_id", "timestamp", "query"],
}

RECENT_ENGAGEMENT_DAYS = 7
LOW_FUTURE_ACTIVITY_DAYS_THRESHOLD = 1


def generate_snapshot_dates(
    min_timestamp: pd.Timestamp,
    max_timestamp: pd.Timestamp,
    observation_days: int,
    label_days: int,
    step_days: int,
    max_snapshots: int | None = None,
) -> list[pd.Timestamp]:
    start = min_timestamp.floor("D") + pd.Timedelta(days=observation_days)
    end = max_timestamp.floor("D") - pd.Timedelta(days=label_days)
    if start >= end:
        raise ValueError("Not enough history to create observation and label windows.")

    snapshots = list(pd.date_range(start=start, end=end, freq=f"{step_days}D"))
    if max_snapshots is not None:
        snapshots = snapshots[-max_snapshots:]
    if len(snapshots) < 3:
        raise ValueError("Need at least three snapshot dates for train/valid/test splits.")
    return snapshots


def assign_time_splits(feature_table: pd.DataFrame) -> pd.DataFrame:
    snapshot_dates = sorted(pd.to_datetime(feature_table["snapshot_date"]).unique())
    count = len(snapshot_dates)
    train_cut = max(1, int(np.floor(count * 0.6)))
    valid_cut = max(train_cut + 1, int(np.floor(count * 0.8)))
    if valid_cut >= count:
        valid_cut = count - 1
    split_map = {}
    for index, snapshot_date in enumerate(snapshot_dates):
        if index < train_cut:
            split_map[snapshot_date] = "train"
        elif index < valid_cut:
            split_map[snapshot_date] = "valid"
        else:
            split_map[snapshot_date] = "test"
    feature_table["split"] = pd.to_datetime(feature_table["snapshot_date"]).map(split_map)
    return feature_table


def _dataset_path(dataset_root: Path, stem: str) -> str:
    return (dataset_root / f"{stem}.parquet").as_posix()


def _create_views(con: duckdb.DuckDBPyConnection, dataset_root: Path) -> None:
    buy_path = _dataset_path(dataset_root, "product_buy")
    cart_path = _dataset_path(dataset_root, "add_to_cart")
    remove_path = _dataset_path(dataset_root, "remove_from_cart")
    page_path = _dataset_path(dataset_root, "page_visit")
    search_path = _dataset_path(dataset_root, "search_query")
    product_path = _dataset_path(dataset_root, "product_properties")

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW product_buy AS
        SELECT CAST(client_id AS BIGINT) AS client_id,
               TRY_CAST(timestamp AS TIMESTAMP) AS ts,
               CAST(sku AS BIGINT) AS sku
        FROM read_parquet('{buy_path}')
        WHERE client_id IS NOT NULL AND sku IS NOT NULL
        """
    )
    con.execute("CREATE OR REPLACE TEMP TABLE buying_users AS SELECT DISTINCT client_id FROM product_buy")

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW add_to_cart AS
        SELECT CAST(a.client_id AS BIGINT) AS client_id,
               TRY_CAST(a.timestamp AS TIMESTAMP) AS ts,
               CAST(a.sku AS BIGINT) AS sku
        FROM read_parquet('{cart_path}') a
        INNER JOIN buying_users b USING (client_id)
        WHERE a.client_id IS NOT NULL AND a.sku IS NOT NULL
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW remove_from_cart AS
        SELECT CAST(r.client_id AS BIGINT) AS client_id,
               TRY_CAST(r.timestamp AS TIMESTAMP) AS ts,
               CAST(r.sku AS BIGINT) AS sku
        FROM read_parquet('{remove_path}') r
        INNER JOIN buying_users b USING (client_id)
        WHERE r.client_id IS NOT NULL AND r.sku IS NOT NULL
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW page_visit AS
        SELECT CAST(p.client_id AS BIGINT) AS client_id,
               TRY_CAST(p.timestamp AS TIMESTAMP) AS ts,
               CAST(p.url AS BIGINT) AS url
        FROM read_parquet('{page_path}') p
        INNER JOIN buying_users b USING (client_id)
        WHERE p.client_id IS NOT NULL
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW search_query AS
        SELECT CAST(s.client_id AS BIGINT) AS client_id,
               TRY_CAST(s.timestamp AS TIMESTAMP) AS ts,
               CAST(s.query AS VARCHAR) AS query
        FROM read_parquet('{search_path}') s
        INNER JOIN buying_users b USING (client_id)
        WHERE s.client_id IS NOT NULL
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW product_properties AS
        SELECT CAST(sku AS BIGINT) AS sku,
               CAST(category AS BIGINT) AS category,
               CAST(price AS DOUBLE) AS price
        FROM read_parquet('{product_path}')
        """
    )


def _infer_bounds(con: duckdb.DuckDBPyConnection) -> tuple[pd.Timestamp, pd.Timestamp]:
    row = con.execute(
        """
        WITH all_ts AS (
            SELECT MIN(ts) AS min_ts, MAX(ts) AS max_ts FROM product_buy
            UNION ALL
            SELECT MIN(ts) AS min_ts, MAX(ts) AS max_ts FROM add_to_cart
            UNION ALL
            SELECT MIN(ts) AS min_ts, MAX(ts) AS max_ts FROM remove_from_cart
            UNION ALL
            SELECT MIN(ts) AS min_ts, MAX(ts) AS max_ts FROM page_visit
            UNION ALL
            SELECT MIN(ts) AS min_ts, MAX(ts) AS max_ts FROM search_query
        )
        SELECT MIN(min_ts) AS min_ts, MAX(max_ts) AS max_ts FROM all_ts
        """
    ).fetchone()
    return pd.Timestamp(row[0]), pd.Timestamp(row[1])


def _create_snapshot_table(con: duckdb.DuckDBPyConnection, snapshots: list[pd.Timestamp]) -> None:
    values = ", ".join([f"(TIMESTAMP '{ts.strftime('%Y-%m-%d %H:%M:%S')}')" for ts in snapshots])
    con.execute(f"CREATE OR REPLACE TEMP TABLE snapshots AS SELECT * FROM (VALUES {values}) AS t(snapshot_date)")


def _active_user_definition_description(active_user_definition: str) -> str:
    descriptions = {
        "historical_buyers": "user had at least one product_buy before the snapshot",
        "recently_active_buyers": "user had at least one product_buy before the snapshot and at least one page_visit/add_to_cart/product_buy in the observation window",
        "recent_engaged_buyers": "user had at least one product_buy in the observation window and at least one page_visit/add_to_cart/product_buy in the last 7 days before the snapshot",
    }
    if active_user_definition not in descriptions:
        raise ValueError(f"Unsupported active_user_definition: {active_user_definition}")
    return descriptions[active_user_definition]


def _churn_definition_description(churn_definition: str) -> str:
    descriptions = {
        "no_buy_in_label_window": "user is churned if there is no product_buy in the next label window",
        "no_buy_and_low_future_activity": "user is churned if there is no product_buy in the next label window and future activity spans at most 1 active day",
    }
    if churn_definition not in descriptions:
        raise ValueError(f"Unsupported churn_definition: {churn_definition}")
    return descriptions[churn_definition]



def _create_active_clients(
    con: duckdb.DuckDBPyConnection,
    active_user_definition: str,
    observation_days: int,
) -> None:
    if active_user_definition == "historical_buyers":
        con.execute(
            """
            CREATE OR REPLACE TEMP TABLE active_clients AS
            SELECT s.snapshot_date, b.client_id
            FROM snapshots s
            JOIN product_buy b ON b.ts < s.snapshot_date
            GROUP BY 1, 2
            """
        )
        return

    if active_user_definition == "recently_active_buyers":
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE historical_buyers_active_base AS
            SELECT s.snapshot_date, b.client_id
            FROM snapshots s
            JOIN product_buy b ON b.ts < s.snapshot_date
            GROUP BY 1, 2
            """
        )
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE recent_activity AS
            SELECT client_id, ts FROM product_buy
            UNION ALL
            SELECT client_id, ts FROM add_to_cart
            UNION ALL
            SELECT client_id, ts FROM page_visit
            """
        )
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE active_clients AS
            SELECT h.snapshot_date, h.client_id
            FROM historical_buyers_active_base h
            JOIN recent_activity a
              ON a.client_id = h.client_id
             AND a.ts >= h.snapshot_date - INTERVAL {observation_days} DAY
             AND a.ts < h.snapshot_date
            GROUP BY 1, 2
            """
        )
        return

    if active_user_definition == "recent_engaged_buyers":
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE observation_window_buyers AS
            SELECT s.snapshot_date, b.client_id
            FROM snapshots s
            JOIN product_buy b
              ON b.ts >= s.snapshot_date - INTERVAL {observation_days} DAY
             AND b.ts < s.snapshot_date
            GROUP BY 1, 2
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TEMP TABLE recent_activity AS
            SELECT client_id, ts FROM product_buy
            UNION ALL
            SELECT client_id, ts FROM add_to_cart
            UNION ALL
            SELECT client_id, ts FROM page_visit
            """
        )
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE recent_engagement AS
            SELECT s.snapshot_date, a.client_id
            FROM snapshots s
            JOIN recent_activity a
              ON a.ts >= s.snapshot_date - INTERVAL {RECENT_ENGAGEMENT_DAYS} DAY
             AND a.ts < s.snapshot_date
            GROUP BY 1, 2
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TEMP TABLE active_clients AS
            SELECT o.snapshot_date, o.client_id
            FROM observation_window_buyers o
            JOIN recent_engagement r USING (snapshot_date, client_id)
            """
        )
        return

    raise ValueError(f"Unsupported active_user_definition: {active_user_definition}")


def _create_labels(con: duckdb.DuckDBPyConnection, label_days: int, churn_definition: str) -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE future_activity AS
        WITH future_events AS (
            SELECT client_id, ts FROM product_buy
            UNION ALL
            SELECT client_id, ts FROM add_to_cart
            UNION ALL
            SELECT client_id, ts FROM page_visit
        )
        SELECT a.snapshot_date,
               a.client_id,
               COUNT(DISTINCT CAST(e.ts AS DATE)) AS future_active_days_14d
        FROM active_clients a
        LEFT JOIN future_events e
          ON e.client_id = a.client_id
         AND e.ts >= a.snapshot_date
         AND e.ts < a.snapshot_date + INTERVAL {label_days} DAY
        GROUP BY 1, 2
        """
    )

    if churn_definition == "no_buy_in_label_window":
        churn_case = "CASE WHEN COUNT(pb.ts) = 0 THEN 1 ELSE 0 END"
    elif churn_definition == "no_buy_and_low_future_activity":
        churn_case = (
            "CASE WHEN COUNT(pb.ts) = 0 "
            f"AND COALESCE(MAX(f.future_active_days_14d), 0) <= {LOW_FUTURE_ACTIVITY_DAYS_THRESHOLD} "
            "THEN 1 ELSE 0 END"
        )
    else:
        raise ValueError(f"Unsupported churn_definition: {churn_definition}")

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE labels AS
        SELECT a.snapshot_date,
               a.client_id,
               COUNT(pb.ts) AS future_buy_count_14d,
               COALESCE(MAX(f.future_active_days_14d), 0) AS future_active_days_14d,
               {churn_case} AS churn
        FROM active_clients a
        LEFT JOIN product_buy pb
          ON pb.client_id = a.client_id
         AND pb.ts >= a.snapshot_date
         AND pb.ts < a.snapshot_date + INTERVAL {label_days} DAY
        LEFT JOIN future_activity f
          ON f.snapshot_date = a.snapshot_date
         AND f.client_id = a.client_id
        GROUP BY 1, 2
        """
    )


def _create_product_event_features(con: duckdb.DuckDBPyConnection, event_name: str, observation_days: int) -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE {event_name}_main AS
        WITH base AS (
            SELECT a.snapshot_date,
                   a.client_id,
                   e.ts,
                   e.sku,
                   pp.category,
                   pp.price
            FROM active_clients a
            LEFT JOIN {event_name} e
              ON e.client_id = a.client_id
             AND e.ts >= a.snapshot_date - INTERVAL {observation_days} DAY
             AND e.ts < a.snapshot_date
            LEFT JOIN product_properties pp
              ON e.sku = pp.sku
        )
        SELECT snapshot_date,
               client_id,
               SUM(CASE WHEN ts >= snapshot_date - INTERVAL 1 DAY THEN 1 ELSE 0 END) AS {event_name}_count_1d,
               SUM(CASE WHEN ts >= snapshot_date - INTERVAL 3 DAY THEN 1 ELSE 0 END) AS {event_name}_count_3d,
               SUM(CASE WHEN ts >= snapshot_date - INTERVAL 7 DAY THEN 1 ELSE 0 END) AS {event_name}_count_7d,
               SUM(CASE WHEN ts >= snapshot_date - INTERVAL 14 DAY THEN 1 ELSE 0 END) AS {event_name}_count_14d,
               SUM(CASE WHEN ts IS NOT NULL THEN 1 ELSE 0 END) AS {event_name}_count_30d,
               COALESCE(DATE_DIFF('day', MAX(ts), snapshot_date), {observation_days + 1}) AS {event_name}_recency_days,
               COUNT(DISTINCT sku) AS {event_name}_distinct_sku_30d,
               COUNT(DISTINCT CAST(ts AS DATE)) AS {event_name}_days_30d,
               COUNT(DISTINCT category) AS {event_name}_distinct_category_30d,
               COALESCE(AVG(price), 0) AS {event_name}_price_mean_30d,
               COALESCE(MAX(price), 0) AS {event_name}_price_max_30d,
               COALESCE(SUM(price), 0) AS {event_name}_price_sum_30d
        FROM base
        GROUP BY 1, 2
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE {event_name}_category_share AS
        WITH category_counts AS (
            SELECT a.snapshot_date,
                   e.client_id,
                   pp.category,
                   COUNT(*) AS cnt
            FROM active_clients a
            JOIN {event_name} e
              ON e.client_id = a.client_id
             AND e.ts >= a.snapshot_date - INTERVAL {observation_days} DAY
             AND e.ts < a.snapshot_date
            JOIN product_properties pp
              ON e.sku = pp.sku
            WHERE pp.category IS NOT NULL
            GROUP BY 1, 2, 3
        )
        SELECT snapshot_date,
               client_id,
               MAX(cnt) * 1.0 / NULLIF(SUM(cnt), 0) AS {event_name}_top_category_share_30d
        FROM category_counts
        GROUP BY 1, 2
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE {event_name}_features AS
        SELECT m.*,
               COALESCE(c.{event_name}_top_category_share_30d, 0) AS {event_name}_top_category_share_30d
        FROM {event_name}_main m
        LEFT JOIN {event_name}_category_share c USING (snapshot_date, client_id)
        """
    )


def _create_page_visit_features(con: duckdb.DuckDBPyConnection, observation_days: int) -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE page_visit_features AS
        WITH base AS (
            SELECT a.snapshot_date,
                   a.client_id,
                   p.ts,
                   p.url
            FROM active_clients a
            LEFT JOIN page_visit p
              ON p.client_id = a.client_id
             AND p.ts >= a.snapshot_date - INTERVAL {observation_days} DAY
             AND p.ts < a.snapshot_date
        )
        SELECT snapshot_date,
               client_id,
               SUM(CASE WHEN ts >= snapshot_date - INTERVAL 1 DAY THEN 1 ELSE 0 END) AS page_visit_count_1d,
               SUM(CASE WHEN ts >= snapshot_date - INTERVAL 3 DAY THEN 1 ELSE 0 END) AS page_visit_count_3d,
               SUM(CASE WHEN ts >= snapshot_date - INTERVAL 7 DAY THEN 1 ELSE 0 END) AS page_visit_count_7d,
               SUM(CASE WHEN ts >= snapshot_date - INTERVAL 14 DAY THEN 1 ELSE 0 END) AS page_visit_count_14d,
               SUM(CASE WHEN ts IS NOT NULL THEN 1 ELSE 0 END) AS page_visit_count_30d,
               COALESCE(DATE_DIFF('day', MAX(ts), snapshot_date), {observation_days + 1}) AS page_visit_recency_days,
               COUNT(DISTINCT CAST(ts AS DATE)) AS page_visit_days_30d,
               COUNT(DISTINCT url) AS page_visit_unique_url_30d
        FROM base
        GROUP BY 1, 2
        """
    )


def _create_search_features(con: duckdb.DuckDBPyConnection, observation_days: int) -> None:
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE search_daily AS
        SELECT client_id,
               CAST(ts AS DATE) AS event_day,
               COUNT(*) AS search_count,
               AVG(LENGTH(query)) AS avg_query_length,
               AVG(
                   CASE
                       WHEN query IS NULL OR LENGTH(TRIM(query)) = 0 THEN 0
                       ELSE 1 + LENGTH(TRIM(query)) - LENGTH(REPLACE(TRIM(query), ' ', ''))
                   END
               ) AS avg_query_word_count
        FROM search_query
        GROUP BY 1, 2
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE cart_days AS
        SELECT DISTINCT client_id, CAST(ts AS DATE) AS event_day
        FROM add_to_cart
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE buy_days AS
        SELECT DISTINCT client_id, CAST(ts AS DATE) AS event_day
        FROM product_buy
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE search_daily_conversion AS
        SELECT s.client_id,
               s.event_day,
               s.search_count,
               s.avg_query_length,
               s.avg_query_word_count,
               CASE WHEN c0.client_id IS NOT NULL OR c1.client_id IS NOT NULL THEN s.search_count ELSE 0 END AS search_to_cart_1d_count,
               CASE WHEN b0.client_id IS NOT NULL OR b1.client_id IS NOT NULL THEN s.search_count ELSE 0 END AS search_to_buy_1d_count
        FROM search_daily s
        LEFT JOIN cart_days c0
          ON c0.client_id = s.client_id AND c0.event_day = s.event_day
        LEFT JOIN cart_days c1
          ON c1.client_id = s.client_id AND c1.event_day = s.event_day + 1
        LEFT JOIN buy_days b0
          ON b0.client_id = s.client_id AND b0.event_day = s.event_day
        LEFT JOIN buy_days b1
          ON b1.client_id = s.client_id AND b1.event_day = s.event_day + 1
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE search_query_features AS
        SELECT a.snapshot_date,
               a.client_id,
               COALESCE(SUM(CASE WHEN s.event_day >= CAST(a.snapshot_date AS DATE) - 1 THEN s.search_count ELSE 0 END), 0) AS search_query_count_1d,
               COALESCE(SUM(CASE WHEN s.event_day >= CAST(a.snapshot_date AS DATE) - 3 THEN s.search_count ELSE 0 END), 0) AS search_query_count_3d,
               COALESCE(SUM(CASE WHEN s.event_day >= CAST(a.snapshot_date AS DATE) - 7 THEN s.search_count ELSE 0 END), 0) AS search_query_count_7d,
               COALESCE(SUM(CASE WHEN s.event_day >= CAST(a.snapshot_date AS DATE) - 14 THEN s.search_count ELSE 0 END), 0) AS search_query_count_14d,
               COALESCE(SUM(s.search_count), 0) AS search_query_count_30d,
               COALESCE(DATE_DIFF('day', MAX(s.event_day), CAST(a.snapshot_date AS DATE)), {observation_days + 1}) AS search_query_recency_days,
               COALESCE(SUM(s.search_count * s.avg_query_length) / NULLIF(SUM(s.search_count), 0), 0) AS search_query_avg_length_30d,
               COALESCE(SUM(s.search_count * s.avg_query_word_count) / NULLIF(SUM(s.search_count), 0), 0) AS search_query_avg_word_count_30d,
               COALESCE(SUM(s.search_to_cart_1d_count), 0) AS search_to_cart_1d_count_30d,
               COALESCE(SUM(s.search_to_buy_1d_count), 0) AS search_to_buy_1d_count_30d
        FROM active_clients a
        LEFT JOIN search_daily_conversion s
          ON s.client_id = a.client_id
         AND s.event_day >= CAST(a.snapshot_date AS DATE) - INTERVAL {observation_days} DAY
         AND s.event_day < CAST(a.snapshot_date AS DATE)
        GROUP BY 1, 2
        """
    )


def _create_active_days_features(con: duckdb.DuckDBPyConnection, observation_days: int) -> None:
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE all_event_days AS
        SELECT client_id, CAST(ts AS DATE) AS event_day FROM product_buy
        UNION
        SELECT client_id, CAST(ts AS DATE) AS event_day FROM add_to_cart
        UNION
        SELECT client_id, CAST(ts AS DATE) AS event_day FROM remove_from_cart
        UNION
        SELECT client_id, CAST(ts AS DATE) AS event_day FROM page_visit
        UNION
        SELECT client_id, CAST(ts AS DATE) AS event_day FROM search_query
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE active_days_features AS
        SELECT a.snapshot_date,
               a.client_id,
               COUNT(DISTINCT d.event_day) AS active_days_30d
        FROM active_clients a
        LEFT JOIN all_event_days d
          ON d.client_id = a.client_id
         AND d.event_day >= CAST(a.snapshot_date AS DATE) - INTERVAL {observation_days} DAY
         AND d.event_day < CAST(a.snapshot_date AS DATE)
        GROUP BY 1, 2
        """
    )


def _materialize_final_table(con: duckdb.DuckDBPyConnection, output_path: Path) -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE final_feature_table AS
        SELECT a.snapshot_date,
               a.client_id,
               l.future_buy_count_14d,
               l.future_active_days_14d,
               l.churn,
               pv.page_visit_count_1d,
               pv.page_visit_count_3d,
               pv.page_visit_count_7d,
               pv.page_visit_count_14d,
               pv.page_visit_count_30d,
               pv.page_visit_recency_days,
               pv.page_visit_days_30d,
               pv.page_visit_unique_url_30d,
               ac.add_to_cart_count_1d,
               ac.add_to_cart_count_3d,
               ac.add_to_cart_count_7d,
               ac.add_to_cart_count_14d,
               ac.add_to_cart_count_30d,
               ac.add_to_cart_recency_days,
               ac.add_to_cart_distinct_sku_30d,
               ac.add_to_cart_days_30d,
               ac.add_to_cart_distinct_category_30d,
               ac.add_to_cart_price_mean_30d,
               ac.add_to_cart_price_max_30d,
               ac.add_to_cart_price_sum_30d,
               ac.add_to_cart_top_category_share_30d,
               rc.remove_from_cart_count_1d,
               rc.remove_from_cart_count_3d,
               rc.remove_from_cart_count_7d,
               rc.remove_from_cart_count_14d,
               rc.remove_from_cart_count_30d,
               rc.remove_from_cart_recency_days,
               rc.remove_from_cart_distinct_sku_30d,
               rc.remove_from_cart_days_30d,
               rc.remove_from_cart_distinct_category_30d,
               rc.remove_from_cart_price_mean_30d,
               rc.remove_from_cart_price_max_30d,
               rc.remove_from_cart_price_sum_30d,
               rc.remove_from_cart_top_category_share_30d,
               pb.product_buy_count_1d,
               pb.product_buy_count_3d,
               pb.product_buy_count_7d,
               pb.product_buy_count_14d,
               pb.product_buy_count_30d,
               pb.product_buy_recency_days,
               pb.product_buy_distinct_sku_30d,
               pb.product_buy_days_30d,
               pb.product_buy_distinct_category_30d,
               pb.product_buy_price_mean_30d,
               pb.product_buy_price_max_30d,
               pb.product_buy_price_sum_30d,
               pb.product_buy_top_category_share_30d,
               sq.search_query_count_1d,
               sq.search_query_count_3d,
               sq.search_query_count_7d,
               sq.search_query_count_14d,
               sq.search_query_count_30d,
               sq.search_query_recency_days,
               sq.search_query_avg_length_30d,
               sq.search_query_avg_word_count_30d,
               sq.search_to_cart_1d_count_30d,
               sq.search_to_buy_1d_count_30d,
               ad.active_days_30d
        FROM active_clients a
        LEFT JOIN labels l USING (snapshot_date, client_id)
        LEFT JOIN page_visit_features pv USING (snapshot_date, client_id)
        LEFT JOIN add_to_cart_features ac USING (snapshot_date, client_id)
        LEFT JOIN remove_from_cart_features rc USING (snapshot_date, client_id)
        LEFT JOIN product_buy_features pb USING (snapshot_date, client_id)
        LEFT JOIN search_query_features sq USING (snapshot_date, client_id)
        LEFT JOIN active_days_features ad USING (snapshot_date, client_id)
        """
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out = output_path.as_posix()
    con.execute(f"COPY final_feature_table TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def _post_process_feature_table(feature_path: Path, config: PipelineConfig) -> Path:
    feature_table = pd.read_parquet(feature_path)
    feature_table["snapshot_date"] = pd.to_datetime(feature_table["snapshot_date"])
    recency_columns = [column for column in feature_table.columns if column.endswith("_recency_days")]
    for column in recency_columns:
        feature_table[column] = feature_table[column].fillna(config.observation_days + 1)
    feature_table = feature_table.fillna(0)
    feature_table = assign_time_splits(feature_table)

    event_prefixes = ["page_visit", "add_to_cart", "remove_from_cart", "product_buy", "search_query"]
    for event_name in event_prefixes:
        count_30d = f"{event_name}_count_30d"
        count_14d = f"{event_name}_count_14d"
        count_7d = f"{event_name}_count_7d"
        count_3d = f"{event_name}_count_3d"

        if count_7d in feature_table.columns and count_30d in feature_table.columns:
            feature_table[f"{event_name}_recent_share_7d_30d"] = safe_divide(
                feature_table[count_7d], feature_table[count_30d]
            )
            previous_23d = (feature_table[count_30d] - feature_table[count_7d]).clip(lower=0)
            recent_rate = feature_table[count_7d] / 7.0
            previous_rate = previous_23d / 23.0
            feature_table[f"{event_name}_trend_delta_7d_vs_prev23d"] = recent_rate - previous_rate
            feature_table[f"{event_name}_trend_ratio_7d_vs_prev23d"] = safe_divide(recent_rate, previous_rate)

        if count_3d in feature_table.columns and count_14d in feature_table.columns:
            feature_table[f"{event_name}_recent_share_3d_14d"] = safe_divide(
                feature_table[count_3d], feature_table[count_14d]
            )
            previous_11d = (feature_table[count_14d] - feature_table[count_3d]).clip(lower=0)
            recent_rate = feature_table[count_3d] / 3.0
            previous_rate = previous_11d / 11.0
            feature_table[f"{event_name}_trend_delta_3d_vs_prev11d"] = recent_rate - previous_rate
            feature_table[f"{event_name}_trend_ratio_3d_vs_prev11d"] = safe_divide(recent_rate, previous_rate)

    if "add_to_cart_count_30d" in feature_table.columns and "page_visit_count_30d" in feature_table.columns:
        feature_table["cart_per_visit_30d"] = safe_divide(
            feature_table["add_to_cart_count_30d"], feature_table["page_visit_count_30d"]
        )
    if "product_buy_count_30d" in feature_table.columns and "add_to_cart_count_30d" in feature_table.columns:
        feature_table["buy_per_cart_30d"] = safe_divide(
            feature_table["product_buy_count_30d"], feature_table["add_to_cart_count_30d"]
        )
    if "product_buy_count_30d" in feature_table.columns and "page_visit_count_30d" in feature_table.columns:
        feature_table["buy_per_visit_30d"] = safe_divide(
            feature_table["product_buy_count_30d"], feature_table["page_visit_count_30d"]
        )
    if "remove_from_cart_count_30d" in feature_table.columns and "add_to_cart_count_30d" in feature_table.columns:
        feature_table["remove_per_cart_30d"] = safe_divide(
            feature_table["remove_from_cart_count_30d"], feature_table["add_to_cart_count_30d"]
        )
    if "add_to_cart_count_30d" in feature_table.columns and "product_buy_count_30d" in feature_table.columns:
        feature_table["cart_abandon_gap_30d"] = (
            feature_table["add_to_cart_count_30d"] - feature_table["product_buy_count_30d"]
        ).clip(lower=0)
    if "search_query_count_30d" in feature_table.columns and "product_buy_count_30d" in feature_table.columns:
        feature_table["search_to_buy_gap_30d"] = (
            feature_table["search_query_count_30d"] - feature_table["product_buy_count_30d"]
        ).clip(lower=0)

    feature_table.to_parquet(feature_path, index=False)
    return feature_path


def build_feature_table(config: PipelineConfig) -> Path:
    config.ensure_directories()
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")

    _create_views(con, config.dataset_root)
    min_timestamp, max_timestamp = _infer_bounds(con)
    snapshots = generate_snapshot_dates(
        min_timestamp=min_timestamp,
        max_timestamp=max_timestamp,
        observation_days=config.observation_days,
        label_days=config.label_days,
        step_days=config.snapshot_step_days,
        max_snapshots=config.max_snapshots,
    )

    _create_snapshot_table(con, snapshots)
    _create_active_clients(con, config.active_user_definition, config.observation_days)
    _create_labels(con, config.label_days, config.churn_definition)
    _create_product_event_features(con, "product_buy", config.observation_days)
    _create_product_event_features(con, "add_to_cart", config.observation_days)
    _create_product_event_features(con, "remove_from_cart", config.observation_days)
    _create_page_visit_features(con, config.observation_days)
    _create_search_features(con, config.observation_days)
    _create_active_days_features(con, config.observation_days)

    feature_path = config.processed_dir / f"{config.output_prefix}_feature_table.parquet"
    _materialize_final_table(con, feature_path)
    feature_path = _post_process_feature_table(feature_path, config)

    row_count = int(con.execute("SELECT COUNT(*) FROM final_feature_table").fetchone()[0])
    feature_count = int(len(pd.read_parquet(feature_path).columns))
    metadata = {
        "dataset_root": str(config.dataset_root),
        "observation_days": config.observation_days,
        "label_days": config.label_days,
        "window_days": config.window_days,
        "snapshot_step_days": config.snapshot_step_days,
        "max_snapshots": config.max_snapshots,
        "sample_frac": config.sample_frac,
        "snapshot_count": len(snapshots),
        "row_count": row_count,
        "feature_count": feature_count,
        "active_user_definition": config.active_user_definition,
        "active_user_definition_detail": _active_user_definition_description(config.active_user_definition),
        "churn_definition": config.churn_definition,
        "churn_definition_detail": _churn_definition_description(config.churn_definition),
    }
    write_json(metadata, config.reports_dir / f"{config.output_prefix}_feature_metadata.json")
    con.close()
    return feature_path

