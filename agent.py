"""
Orchestrates Claude 3.5 Sonnet as the reasoning core for the text-to-SQL agent.

Flow per question:
  1. Claude is given the two tools (get_db_schema, run_sql_query) and the
     user's natural-language question — but NOT the schema itself.
  2. Claude calls get_db_schema for the tables it thinks are relevant.
  3. Claude writes a SELECT query and calls run_sql_query.
  4. If the query errors, the error text is fed straight back to Claude in
     the next turn, and it retries with a corrected query. This retry step
     is capped (MAX_RETRIES) to avoid infinite loops on a persistently bad
     query — a known edge case worth calling out in review.

Requires ANTHROPIC_API_KEY to be set in the environment.
"""
import os
import json
import anthropic
from server import get_db_schema_impl, run_sql_query_impl

MAX_RETRIES = 3
MODEL = "claude-3-5-sonnet-20241022"

TOOLS = [
    {
        "name": "get_db_schema",
        "description": "Get table definitions, keys, and sample rows for given tables. "
                        "Call with no arguments first to list available tables.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tables to inspect. Omit to just list table names.",
                }
            },
        },
    },
    {
        "name": "run_sql_query",
        "description": "Execute a read-only SELECT query against the database.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]

SYSTEM_PROMPT = (
    "You are a SQL analyst agent. You answer business questions by writing and "
    "running SQL queries against a database you don't yet know the schema of. "
    "Always call get_db_schema first to discover relevant tables before writing "
    "SQL. If run_sql_query returns an ERROR, read the error, fix your query, and "
    "call run_sql_query again. Once you have the result, answer the user's "
    "question in one clear sentence, plus the final SQL query you used."
)


def _execute_tool(name: str, tool_input: dict) -> str:
    if name == "get_db_schema":
        return get_db_schema_impl(tool_input.get("table_names"))
    if name == "run_sql_query":
        return run_sql_query_impl(tool_input["query"])
    return f"ERROR: unknown tool {name}"


def answer_question(question: str, verbose: bool = True) -> dict:
    """Run the agent loop for a single question. Returns dict with final answer,
    the SQL used, whether it errored at least once, and retry count."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    messages = [{"role": "user", "content": question}]
    retries = 0
    had_error = False
    last_query = None

    for _turn in range(MAX_RETRIES + 4):  # a few extra turns for schema lookups
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {
                "answer": final_text,
                "sql": last_query,
                "had_error": had_error,
                "retries": retries,
            }

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if verbose:
                print(f"  [tool call] {block.name}({block.input})")
            if block.name == "run_sql_query":
                last_query = block.input.get("query")
            result_text = _execute_tool(block.name, block.input)
            if block.name == "run_sql_query" and result_text.startswith("ERROR"):
                had_error = True
                retries += 1
                if retries > MAX_RETRIES:
                    result_text += "\nMax retries exceeded. Report failure to the user."
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})

    return {"answer": "Agent did not converge in time.", "sql": last_query,
            "had_error": had_error, "retries": retries}


if __name__ == "__main__":
    q = "Which product category had the highest return rate in Karnataka?"
    result = answer_question(q)
    print(json.dumps(result, indent=2))
