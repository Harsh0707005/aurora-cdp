"""Pydantic response models for the profile API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Health(BaseModel):
    status: str = "ok"
    lake_root: str
    tables: dict[str, bool]
    latest_job: str | None = None


class SourceRecord(BaseModel):
    datasource: str
    pk: str
    aurora_id: str
    given_name: str | None = None
    surname: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    postal: str | None = None
    birthdate: str | None = None
    loyalty_id: str | None = None
    updated_at: str | None = None


class Profile(BaseModel):
    aurora_id: str
    golden: dict[str, Any]
    records: list[SourceRecord]
    sources: list[str]
    record_count: int
    is_supersized: bool = False
    lineage: list[dict[str, Any]] = Field(default_factory=list)


class SearchHit(BaseModel):
    aurora_id: str
    given_name: str | None = None
    surname: str | None = None
    email: str | None = None
    phone: str | None = None
    record_count: int


class ClusterView(BaseModel):
    cluster_id: str
    aurora_id: str
    records: list[SourceRecord]
    edges: list[dict[str, Any]]


class ResolveRequest(BaseModel):
    records: list[dict[str, Any]]


class ResolveResponse(BaseModel):
    results: list[dict[str, Any]]
