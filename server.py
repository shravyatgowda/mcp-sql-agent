"""
MCP server that gives an LLM schema-aware, read-only access to a SQL database.

Design principles (matching the production version described on the resume):
  1. Never dump the full schema into the prompt up front. The LLM calls
     `get_db_schema` on demand for just the tables it needs, which keeps
     token usage low and avoids hallucinated column names.
  2. Every query is read-only (SELECT-only, enforced). Any SQL error is
     returned as structured text so the calling agent can self-correct
     instead of failing silently — this is the "self-healing loop."

Run as a standalone MCP server:
    python server.py

Or import `get_db_schema` / `run_sql_query` directly (see eval/run_eval.py).
"""
import os
import re
import sqlite3
from typing import Optional
from mcp.server.fastmcp import FastMCP

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "db", "demo.db")

mcp = FastMCP("sql-agent")

_READ_ONLY_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_schema_impl(table_names: Optional[list] = None) -> str:
    conn = _connect()
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = [r["name"] for r in cur.fetchall()]

    if not table_names:
        conn.close()
        return ("Available tables: " + ", ".join(all_tables) +
                "\nCall get_db_schema(table_names=[...]) to see columns and sample rows.")

    output = []
    for table in table_names:
        if table not in all_tables:
            output.append(f"-- Table '{table}' not found. Available: {all_tables}")
            continue

        cur.execute(f"PRAGMA table_info({table})")
        cols = cur.fetchall()
        col_lines = [f"  {c['name']} ({c['type']}){' PRIMARY KEY' if c['pk'] else ''}" for c in cols]

        cur.execute(f"PRAGMA foreign_key_list({table})")
        fks = cur.fetchall()
        fk_lines = [f"  FOREIGN KEY {fk['from']} -> {fk['table']}({fk['to']})" for fk in fks]

        cur.execute(f"SELECT * FROM {table} LIMIT 3")
        sample_rows = [dict(r) for r in cur.fetchall()]

        output.append(
            f"TABLE {table}:\n" + "\n".join(col_lines) +
            (("\n" + "\n".join(fk_lines)) if fk_lines else "") +
            f"\nSAMPLE ROWS: {sample_rows}"
        )

    conn.close()
    return "\n\n".join(output)


def run_sql_query_impl(query: str) -> str:
    if not _READ_ONLY_PATTERN.match(query):
        return "ERROR: Only SELECT statements are permitted through this tool."

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(query)
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return "Query executed successfully. 0 rows returned."
        return f"Query executed successfully. {len(rows)} row(s):\n{rows[:50]}"
    except sqlite3.Error as e:
        return f"ERROR: {e}"
    finally:
        conn.close()


@mcp.tool()
def get_db_schema(table_names: Optional[list] = None) -> str:
    """Return table definitions, keys, and 3 sample rows for the requested tables.
    If table_names is omitted, returns just the list of available table names."""
    return get_db_schema_impl(table_names)


@mcp.tool()
def run_sql_query(query: str) -> str:
    """Execute a read-only SELECT query and return the result set as text.
    On failure, returns the raw database error so the caller can self-correct."""
    return run_sql_query_impl(query)


if __name__ == "__main__":
    mcp.run()
