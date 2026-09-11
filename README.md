# Autonomous SQL-Agent & MCP Server

A Python [MCP](https://modelcontextprotocol.io) server that gives an LLM
schema-aware, read-only access to a SQL database, so non-technical users can
ask business questions in plain English and get back the exact data table.

Built as a portfolio version of a production pattern used in real client
data-pipeline work — same architecture, demo data.

## Why this exists

Naively dumping an entire database schema into an LLM prompt wastes tokens
and increases hallucinated column/table names on anything but a toy schema.
This server instead exposes two tools and lets the model decide when to use
them:

- **`get_db_schema(table_names=None)`** — called with no arguments, returns
  just the list of table names. Called with specific table names, returns
  those tables' columns, primary/foreign keys, and 3 sample rows. The model
  only pulls in the schema detail it actually needs for the question at hand.
- **`run_sql_query(query)`** — executes a **read-only** SQL query (anything
  that isn't a `SELECT` is rejected before it touches the database) and
  returns the result set as text.

## The self-healing loop

If `run_sql_query` returns a SQL error (bad column name, syntax issue, etc.),
that error text is fed straight back to the model on the next turn instead
of failing the request. The model reads the error and retries with a
corrected query. `agent.py` caps this at `MAX_RETRIES = 3` — an important
edge case to flag in review, since an uncapped retry loop on a persistently
malformed query would burn tokens indefinitely without ever getting a useful
answer back to the user.

## Architecture

```
User question
     │
     ▼
Claude 3.5 Sonnet (agent.py) ── system prompt instructs: always check
     │                          schema before writing SQL
     ├──> get_db_schema tool ──> server.py ──> demo.db (SQLite)
     │
     ├──> run_sql_query tool ──> server.py ──> demo.db (SQLite)
     │        │
     │        └── on ERROR, error text returned to model → retry (≤3x)
     │
     ▼
Final answer + SQL used
```

The demo database (`db/demo.db`) is SQLite for portability; `server.py` is
written so the connection layer is the only thing that would need to change
to point at PostgreSQL/MySQL in production (this project's production
counterpart ran against PostgreSQL).

## Evaluation methodology

`eval/benchmark.json` contains a set of natural-language business questions
mapped to hand-written ground-truth SQL (15 questions are included in this
public repo as a representative sample of the original 50-question internal
benchmark).

**Accuracy is measured as execution/result accuracy, not string accuracy.**
The generated query does not need to match the ground-truth query
character-for-character — it's scored correct if executing it returns the
*identical result set* as the ground truth. A query using a different but
equivalent JOIN structure, alias names, or column order that still returns
the same rows counts as correct.

Run it yourself:

```bash
pip install -r requirements.txt
python db/seed.py
export ANTHROPIC_API_KEY=sk-...
python eval/run_eval.py
```

This writes `eval/results.json` with per-question pass/fail and retry counts.

## Project structure

```
mcp-sql-agent/
├── server.py          # MCP server: schema + query tools
├── agent.py            # Claude orchestration + self-healing retry loop
├── db/
│   ├── schema.sql       # demo retail schema
│   └── seed.py          # generates db/demo.db with 4,000 synthetic orders
├── eval/
│   ├── benchmark.json    # sample text-to-SQL evaluation set
│   └── run_eval.py       # runs the benchmark, computes execution accuracy
└── requirements.txt
```

## Honest limitations

- The retry loop can still get stuck retrying the *same category* of error
  if the model misdiagnoses the root cause — the cap prevents runaway cost,
  but doesn't guarantee eventual success.
- `run_sql_query` blocks non-`SELECT` statements at the string level (regex
  on the leading keyword). A production deployment against a real database
  should additionally run the connection itself under a read-only DB role,
  rather than relying on the guard in this layer alone.
- The demo dataset is synthetic; the accuracy figure is meaningful for this
  benchmark and schema, not as a general text-to-SQL benchmark claim.
