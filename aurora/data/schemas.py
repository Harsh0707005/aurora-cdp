"""Shared column definitions and Spark schemas for the Aurora data model."""

from __future__ import annotations

from pyspark.sql import types as T

# Semantic profile columns every source is mapped onto before Stitch.
SEMANTIC_COLUMNS = [
    "given_name", "surname", "full_name", "email", "phone", "address", "city", "state",
    "postal", "country", "birthdate", "loyalty_id", "gender", "updated_at",
]

# Standardised derivatives produced by preprocessing.
STD_COLUMNS = [
    "email_std", "email_canon", "phone_std", "given_std", "surname_std", "given_nick",
    "street_std", "house_no", "postal_std", "dob_std",
]

PK_COLUMNS = ["datasource", "pk"]

RAW_SCHEMA = T.StructType(
    [T.StructField(c, T.StringType(), True) for c in PK_COLUMNS + SEMANTIC_COLUMNS]
    + [T.StructField("truth_id", T.StringType(), True)]
)

PAIR_FEATURE_COLUMNS = [
    "email_exact", "email_sim", "phone_exact", "phone_prefix", "given_jw", "surname_jw",
    "name_exact", "nickname_match", "postal_eq", "house_eq", "street_sim", "dob_eq", "dob_near",
    "fk_match", "name_conflict", "given_conflict", "dob_conflict",
]

MATCH_CATEGORIES = {0: "non_match", 1: "weak", 2: "moderate", 3: "high", 4: "excellent", 5: "exact"}

TABLES = {
    "unified_preprocessed_raw": "Unified_Preprocessed_Raw",
    "unified_coalesced": "Unified_Coalesced",
    "unified_customer": "Unified_Customer",
    "merged_customers": "Merged_Customers",
    "stitch_scores": "Stitch_Scores",
    "unified_changes_clusters": "Unified_Changes_Clusters",
    "unified_changes_pks": "Unified_Changes_PKs",
    "customer360": "Customer360",
    "stable_id_mapping": "Stable_Id_Mapping",
    "lineage": "Lineage",
    "blocking_stats": "Blocking_Stats",
}
