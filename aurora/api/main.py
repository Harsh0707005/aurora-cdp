"""FastAPI profile API + minimal server-rendered explorer UI.

Reads lake tables without Spark (``aurora.io.deltaio.read_table_pandas``) and
caches them in memory; ``POST /admin/reload`` refreshes after a new run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aurora.api.models import ClusterView, Health, Profile, ResolveRequest, ResolveResponse, SearchHit, SourceRecord
from aurora.config.schema import load_config
from aurora.data.schemas import PAIR_FEATURE_COLUMNS, TABLES
from aurora.features.pairwise import pair_features
from aurora.io.deltaio import read_table_pandas, table_exists
from aurora.scoring.ordinal import build_scorer
from aurora.utils import standardize as S

CONFIG_PATH = os.environ.get("AURORA_CONFIG", "configs/tenants/demo.yaml")
HERE = Path(__file__).parent
app = FastAPI(title="Aurora CDP", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
templates = Jinja2Templates(directory=str(HERE / "templates"))

RECORD_COLS = ["datasource", "pk", "aurora_id", "given_name", "surname", "email", "phone", "address", "postal",
               "birthdate", "loyalty_id", "updated_at", "email_std", "email_canon", "phone_std", "given_std",
               "surname_std", "cluster_id"]


class Store:
    """In-memory snapshot of the lake tables used by the API."""

    def __init__(self) -> None:
        self.cfg = load_config(CONFIG_PATH)
        self.lake = self.cfg.storage.lake_root
        self.unified = pd.DataFrame()
        self.merged = pd.DataFrame()
        self.lineage = pd.DataFrame()
        self.scores = pd.DataFrame()
        self.reload()

    def reload(self) -> None:
        self.unified = read_table_pandas(self.lake, TABLES["unified_customer"], columns=RECORD_COLS)
        self.merged = read_table_pandas(self.lake, TABLES["customer360"])
        self.lineage = read_table_pandas(self.lake, TABLES["stable_id_mapping"])
        self.scores = read_table_pandas(
            self.lake, TABLES["stitch_scores"],
            columns=["datasource_l", "pk_l", "datasource_r", "pk_r", "score", "match_category", "match_type"],
        )
        if not self.unified.empty:
            self.unified = self.unified.astype(object).where(pd.notna(self.unified), None)
            self._by_id = self.unified.groupby("aurora_id").indices
            # groupby drops null keys itself; positions must stay relative to self.unified for iloc
            self._by_email = self.unified.groupby("email_canon").indices
            self._by_phone = self.unified.groupby("phone_std").indices
            self._by_cluster = self.unified.groupby("cluster_id").indices
            self.merged = self.merged.astype(object).where(pd.notna(self.merged), None).set_index("aurora_id", drop=False)
        else:
            self._by_id = self._by_email = self._by_phone = self._by_cluster = {}

    @property
    def ready(self) -> bool:
        return not self.unified.empty

    def latest_job(self) -> str | None:
        p = Path("data/runs/LATEST")
        return p.read_text().strip() if p.exists() else None

    def records_for(self, aurora_id: str) -> list[dict[str, Any]]:
        idx = self._by_id.get(aurora_id)
        if idx is None:
            return []
        return self.unified.iloc[idx].to_dict("records")

    def profile(self, aurora_id: str) -> Profile | None:
        recs = self.records_for(aurora_id)
        if not recs:
            return None
        golden = self.merged.loc[aurora_id].to_dict() if aurora_id in self.merged.index else {}
        golden = {k: (list(v) if hasattr(v, "tolist") else v) for k, v in golden.items()}
        lin = self.lineage[self.lineage["aurora_id"] == aurora_id].sort_values("job_id").to_dict("records") \
            if not self.lineage.empty else []
        return Profile(
            aurora_id=aurora_id, golden=golden, records=[SourceRecord(**r) for r in recs],
            sources=sorted({r["datasource"] for r in recs}), record_count=len(recs),
            is_supersized=bool(golden.get("is_supersized") or False), lineage=lin,
        )

    def search(self, email: str | None, phone: str | None, name: str | None, limit: int = 25) -> list[SearchHit]:
        ids: set[str] = set()
        if email:
            key = S.canonical_email(email)
            ids |= {self.unified.iloc[i]["aurora_id"] for i in self._by_email.get(key, [])}
        if phone:
            key = S.normalize_phone(phone)
            ids |= {self.unified.iloc[i]["aurora_id"] for i in self._by_phone.get(key, [])}
        if name and not ids:
            given, surname = S.split_full_name(name)
            m = self.unified
            if surname:
                m = m[m["surname_std"] == surname]
            if given:
                m = m[m["given_std"] == given]
            ids |= set(m["aurora_id"].head(limit * 5))
        hits = []
        for aid in sorted(ids)[:limit]:
            recs = self.records_for(aid)
            g = self.merged.loc[aid] if aid in self.merged.index else {}
            hits.append(SearchHit(aurora_id=aid, given_name=g.get("given_name"), surname=g.get("surname"),
                                  email=g.get("email"), phone=g.get("phone"), record_count=len(recs)))
        return hits

    def cluster(self, cluster_id: str) -> ClusterView | None:
        try:
            cid = int(cluster_id)
        except ValueError:
            # allow lookup by aurora_id too
            recs = self.records_for(cluster_id)
            if not recs:
                return None
            cid = int(recs[0]["cluster_id"])
        idx = self._by_cluster.get(cid)
        if idx is None:
            return None
        recs = self.unified.iloc[idx].to_dict("records")
        keys = {(r["datasource"], r["pk"]) for r in recs}
        edges = []
        if not self.scores.empty:
            s = self.scores
            m = s[[(a, b) in keys and (c, d) in keys for a, b, c, d in
                   zip(s["datasource_l"], s["pk_l"], s["datasource_r"], s["pk_r"], strict=True)]]
            edges = m.to_dict("records")
        return ClusterView(cluster_id=str(cid), aurora_id=recs[0]["aurora_id"],
                           records=[SourceRecord(**r) for r in recs], edges=edges)

    def resolve(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Score each incoming record against candidates sharing email/phone and return the best match."""
        scorer = build_scorer(self.cfg.scoring)
        out = []
        for raw in records:
            given, surname = raw.get("given_name"), raw.get("surname")
            if (not given or not surname) and raw.get("full_name"):
                g2, s2 = S.split_full_name(raw["full_name"])
                given, surname = given or g2, surname or s2
            email = S.normalize_email(raw.get("email"))
            std = {
                "email_std": email, "email_canon": S.canonical_email(email),
                "phone_std": S.normalize_phone(raw.get("phone")),
                "given_std": S.normalize_name(given), "surname_std": S.normalize_name(surname),
                "given_nick": S.normalize_name(given, self.cfg.nicknames) if given else None,
                "street_std": S.normalize_street(raw.get("address")), "house_no": S.house_number(raw.get("address")),
                "postal_std": S.normalize_postal(raw.get("postal")), "dob_std": S.normalize_dob(raw.get("birthdate")),
                "loyalty_id": raw.get("loyalty_id"),
            }
            cand_idx: set[int] = set()
            if std["email_canon"]:
                cand_idx |= set(self._by_email.get(std["email_canon"], []))
            if std["phone_std"]:
                cand_idx |= set(self._by_phone.get(std["phone_std"], []))
            if not cand_idx and std["surname_std"]:
                m = self.unified[self.unified["surname_std"] == std["surname_std"]]
                cand_idx |= set(m.index[:200])
            best = None
            if cand_idx:
                cands = self.unified.iloc[sorted(cand_idx)]
                feats = pd.DataFrame([pair_features(std, {**c, "given_nick": S.normalize_name(c.get("given_std"), self.cfg.nicknames) if c.get("given_std") else None})
                                      for c in cands.to_dict("records")], columns=PAIR_FEATURE_COLUMNS)
                sc = scorer.score(feats)
                i = int(sc["score"].idxmax())
                if sc.loc[i, "score"] >= self.cfg.scoring.edge_keep_threshold:
                    best = {"aurora_id": cands.iloc[i]["aurora_id"], "score": float(sc.loc[i, "score"]),
                            "match_category": sc.loc[i, "match_category"], "match_type": sc.loc[i, "match_type"],
                            "matched_record": {"datasource": cands.iloc[i]["datasource"], "pk": cands.iloc[i]["pk"]}}
            out.append({"input": raw, "match": best, "candidates": len(cand_idx)})
        return out


store = Store()


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(lake_root=store.lake, latest_job=store.latest_job(),
                  tables={t: table_exists(store.lake, t) for t in TABLES.values()})


# by_pk must be registered before the parametrised route or 'by_pk' is taken as an aurora_id
@app.get("/profiles/by_pk", response_model=Profile)
def profile_by_pk(datasource: str, pk: str) -> Profile:
    m = store.unified[(store.unified["datasource"] == datasource) & (store.unified["pk"] == pk)]
    if m.empty:
        raise HTTPException(404, "unknown (datasource, pk)")
    return store.profile(m.iloc[0]["aurora_id"])  # type: ignore[return-value]


@app.get("/profiles/{aurora_id}", response_model=Profile)
def get_profile(aurora_id: str) -> Profile:
    p = store.profile(aurora_id)
    if p is None:
        raise HTTPException(404, "unknown aurora_id")
    return p


@app.get("/search", response_model=list[SearchHit])
def search(email: str | None = None, phone: str | None = None, name: str | None = None,
           limit: int = Query(25, le=200)) -> list[SearchHit]:
    if not (email or phone or name):
        raise HTTPException(400, "provide email, phone or name")
    return store.search(email, phone, name, limit)


@app.get("/clusters/{cluster_id}", response_model=ClusterView)
def get_cluster(cluster_id: str) -> ClusterView:
    c = store.cluster(cluster_id)
    if c is None:
        raise HTTPException(404, "unknown cluster")
    return c


@app.post("/resolve", response_model=ResolveResponse)
def resolve(req: ResolveRequest) -> ResolveResponse:
    return ResolveResponse(results=store.resolve(req.records))


@app.post("/admin/reload")
def reload_tables() -> dict[str, Any]:
    store.reload()
    return {"status": "reloaded", "records": int(len(store.unified)), "latest_job": store.latest_job()}


@app.post("/admin/run")
def admin_run(raw: str = "data/raw/run1") -> JSONResponse:
    """Trigger a local pipeline run (blocking) and reload tables."""
    cmd = [sys.executable, "-m", "aurora.pipeline.runner", "--config", CONFIG_PATH, "--raw", raw]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    tail = "\n".join(proc.stdout.splitlines()[-3:])
    if proc.returncode != 0:
        return JSONResponse({"status": "failed", "stderr": proc.stderr[-2000:]}, status_code=500)
    store.reload()
    return JSONResponse({"status": "ok", "summary": tail, "latest_job": store.latest_job()})


# ------------------------------------------------------------------ UI


@app.get("/", response_class=HTMLResponse)
def ui_home(request: Request):
    return templates.TemplateResponse(request, "search.html", {"ready": store.ready, "job": store.latest_job(),
                                                               "records": len(store.unified),
                                                               "clusters": len(store._by_id)})


@app.get("/ui/search", response_class=HTMLResponse)
def ui_search(request: Request, q: str = ""):
    q = q.strip()
    hits = []
    if q:
        if q in store._by_id:
            hits = [SearchHit(aurora_id=q, record_count=len(store.records_for(q)))]
        elif "@" in q:
            hits = store.search(q, None, None)
        elif sum(ch.isdigit() for ch in q) >= 7:
            hits = store.search(None, q, None)
        else:
            hits = store.search(None, None, q)
    return templates.TemplateResponse(request, "_results.html", {"hits": hits, "q": q})


@app.get("/ui/profile/{aurora_id}", response_class=HTMLResponse)
def ui_profile(request: Request, aurora_id: str):
    p = store.profile(aurora_id)
    if p is None:
        raise HTTPException(404, "unknown aurora_id")
    return templates.TemplateResponse(request, "profile.html", {"p": p})


@app.get("/ui/cluster/{cluster_id}", response_class=HTMLResponse)
def ui_cluster(request: Request, cluster_id: str):
    c = store.cluster(cluster_id)
    if c is None:
        raise HTTPException(404, "unknown cluster")
    return templates.TemplateResponse(request, "cluster.html", {"c": c})
