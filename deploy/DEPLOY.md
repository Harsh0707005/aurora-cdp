# Deployment

Two layers: a **compose stack** (API + UI, job runner, Postgres, seed) that runs anywhere Docker runs, and
**AWS material** (scripts under `deploy/aws/`) that stands the same stack up on EC2 with S3 as the raw landing
zone and RDS Postgres as the serving/metadata store. Nothing here has been executed against a live account;
every cloud step is credentials-gated and scripted so the organisation can run it deliberately.

## 1. Local / any Docker host

```bash
docker compose -f docker/docker-compose.yml up --build
# UI http://localhost:8000/ui · API docs http://localhost:8000/docs · Postgres localhost:5432 (aurora/aurora)
```
See `docker/README.md` for service roles, re-seeding and the DuckDB single-writer note.

## 2. AWS (EC2 + compose, S3 landing, RDS Postgres)

Prerequisites: `aws` CLI v2 configured (`aws sts get-caller-identity` works), an EC2 key pair, Docker locally
is *not* required (the host builds the image).

```bash
cp deploy/aws/env.example deploy/aws/.env    # edit: bucket name, key pair, RDS password, allowed CIDR
cd deploy/aws
./01_s3_landing.sh          # versioned, encrypted, private bucket; raw/<source>/<feed>/<date>/ layout
./03_ec2_compose.sh         # SG (22, 8000 from ALLOWED_CIDR), IAM role (S3 landing + SSM), t3.large AL2023 host
./02_rds_postgres.sh        # db.t3.micro Postgres 16, private, encrypted, 7-day backups, deletion protection
./04_deploy_code.sh <ip>    # upload tracked code, write .env, start systemd unit -> compose stack, health check
```

Order note: run `03` before `02` so the RDS security group can allow 5432 from the EC2 security group
(re-run `02` after `03` if you ran them the other way round; it is idempotent).

What each resource is for:

| Resource | Role | Script |
|---|---|---|
| S3 `RAW_BUCKET` | immutable raw landing zone for feeds (`raw/<source>/<feed>/<yyyy-mm-dd>/*.csv`); `sync_feeds.sh` pulls and ingests | `01` |
| EC2 host | runs `docker/docker-compose.yml`: API+UI :8000, runner, seed; DuckDB on an encrypted gp3 volume at `/data` | `03`, `04`, `user_data.sh` |
| RDS Postgres | serving / metadata store (see "Serving layer") | `02` |
| IAM role | instance profile with S3 landing read/write and SSM Session Manager (no inbound SSH needed if you close 22) | `03` |

Operate:

```bash
ssh ec2-user@<ip> 'cd /opt/aurora-cdp && docker compose -f docker/docker-compose.yml logs -f runner'
ssh ec2-user@<ip> 'cd /opt/aurora-cdp && docker compose -f docker/docker-compose.yml run --rm api aurora report'
./sync_feeds.sh crm customers mappings/crm.yaml incremental     # on the host, pulls s3://RAW_BUCKET/raw/crm/customers/
./destroy.sh                                                    # terminates EC2, deletes RDS with final snapshot; keeps bucket
```

Cost guard-rails: defaults are t3.large + db.t3.micro + 50 GB gp3 (roughly $80–100/month in us-east-1 if left
running). `destroy.sh` exists so dev environments are not left running.

## 3. ECS alternative

For a managed runtime, build/push the image to ECR and run two services from the same task definition
(API: `uvicorn ...`; runner: `aurora schedule ...`) with an EFS volume mounted at `/data` for the DuckDB file.
Because DuckDB is single-writer, keep the runner at 1 task and the API read-only (it already uses read-only
connections) or move the serving reads to Postgres first. Not scripted yet.

## 4. Serving layer (TODO)

Postgres is provisioned (compose `db`, RDS) as the target for serving reads and run metadata so the API can
scale independently of the DuckDB writer. Planned sync after each pipeline run: `customer_360`,
`identity_graph`, `unified_changes_pk/clusters`, `segment_members`, `stitch_runs` via `COPY`. The DDL in
`aurora_cdp/storage/schema.sql` is already Postgres/Snowflake-compatible for those tables.

## 5. Security notes

- No credentials in the repo: `deploy/aws/.env` is git-ignored; RDS password is passed through the host `.env`.
- Bucket blocks public access, versioned, SSE-S3. RDS is not publicly accessible.
- Restrict `ALLOWED_CIDR`; prefer SSM Session Manager over port 22.
- The demo seed data is synthetic; point `sync_feeds.sh` at real feeds only after reviewing retention needs
  (bronze keeps every landed row).
