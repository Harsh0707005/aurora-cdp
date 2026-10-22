Place forward-only migrations here as `V<nnn>__<description>.sql` (V001 is `../schema.sql`).
`aurora_cdp.storage.duck.init_schema` applies them in lexical order and records each in `schema_version`.
