"""
Vertex AI SDK Analytics Agent — natural language to BigQuery SQL.
Used in Tutorial 5.3: Multi-Turn Agents with the Vertex AI SDK.

The agent uses Gemini function calling to:
  1. List available BigQuery tables (if needed)
  2. Write and execute SQL queries against the retail_analytics dataset
  3. Explain results in natural language

Usage (interactive CLI):
  python3 analytics_agent.py --project=YOUR_PROJECT_ID

Usage (single question):
  python3 analytics_agent.py --project=YOUR_PROJECT_ID \
    --question="What were the top 5 products by revenue last month?"
"""

import argparse
import json
import logging
import subprocess

import vertexai
from google.cloud import bigquery
from vertexai.generative_models import (
    FunctionDeclaration,
    GenerativeModel,
    Part,
    Tool,
)

logging.basicConfig(level=logging.WARNING)


# ── Tool implementations ───────────────────────────────────────────────────

def make_tools(project: str, dataset: str):
    bq_client = bigquery.Client(project=project)

    def run_sql(query: str) -> str:
        """Execute a BigQuery SQL query and return results as JSON."""
        try:
            df = bq_client.query(query).to_dataframe()
            return df.head(20).to_json(orient="records", date_format="iso")
        except Exception as e:
            return json.dumps({"error": str(e)})

    def list_tables() -> str:
        """List all tables in the retail_analytics dataset."""
        tables = list(bq_client.list_tables(f"{project}.{dataset}"))
        return json.dumps([t.table_id for t in tables])

    tool_functions = {
        "run_sql":     run_sql,
        "list_tables": list_tables,
    }

    run_sql_decl = FunctionDeclaration(
        name="run_sql",
        description=(
            f"Execute a GoogleSQL query against the `{project}.{dataset}` BigQuery dataset. "
            "Use this to answer questions about sales, revenue, products, and stores. "
            "Always add a LIMIT 20 clause unless the user explicitly asks for more rows."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        f"A valid GoogleSQL query. Table references must be fully qualified: "
                        f"`{project}.{dataset}.table_name`"
                    )
                }
            },
            "required": ["query"],
        },
    )

    list_tables_decl = FunctionDeclaration(
        name="list_tables",
        description=f"List all available tables in the `{project}.{dataset}` BigQuery dataset.",
        parameters={"type": "object", "properties": {}},
    )

    vertex_tool = Tool(function_declarations=[run_sql_decl, list_tables_decl])
    return tool_functions, vertex_tool


# ── Agent loop ─────────────────────────────────────────────────────────────

def build_agent(project: str, dataset: str):
    tool_functions, vertex_tool = make_tools(project, dataset)

    model = GenerativeModel(
        "gemini-1.5-pro",
        tools=[vertex_tool],
        system_instruction=f"""You are a helpful data analytics assistant with access
to the '{dataset}' BigQuery dataset in project '{project}'.

When answering questions:
1. If you don't know the schema, call list_tables() first, then inspect columns.
2. Write precise GoogleSQL queries — fully qualify table names as
   `{project}.{dataset}.table_name`.
3. After receiving query results, explain them clearly in plain language.
4. If the data is insufficient to answer, say so and suggest what data would help.
5. Keep answers concise. Show the key numbers, not the raw JSON."""
    )

    def run_agent(question: str, verbose: bool = True) -> str:
        chat = model.start_chat()
        messages = [question]

        for _ in range(10):   # max 10 tool-call rounds
            response = chat.send_message(messages)
            candidate = response.candidates[0]

            parts = candidate.content.parts
            if not parts:
                return "(no response)"

            fn_call = parts[0].function_call
            if fn_call and fn_call.name:
                fn_name = fn_call.name
                fn_args = dict(fn_call.args) if fn_call.args else {}

                if verbose:
                    args_str = json.dumps(fn_args)[:120]
                    print(f"\n  [tool] {fn_name}({args_str})")

                result = tool_functions[fn_name](**fn_args)

                if verbose:
                    preview = result[:200] + "..." if len(result) > 200 else result
                    print(f"  [result] {preview}")

                messages = [Part.from_function_response(
                    name=fn_name,
                    response={"content": result},
                )]
            else:
                return parts[0].text

        return "(max tool-call rounds reached)"

    return run_agent


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Retail analytics natural language agent")
    parser.add_argument("--project",  required=True, help="GCP project ID")
    parser.add_argument("--dataset",  default="retail_analytics", help="BigQuery dataset")
    parser.add_argument("--question", default="", help="Single question (omit for interactive mode)")
    parser.add_argument("--quiet",    action="store_true", help="Suppress tool-call logs")
    args = parser.parse_args()

    vertexai.init(project=args.project, location="us-central1")

    run_agent = build_agent(args.project, args.dataset)

    if args.question:
        answer = run_agent(args.question, verbose=not args.quiet)
        print(f"\nAnswer: {answer}")
        return

    # Interactive mode
    print(f"Data Analytics Agent — dataset: {args.project}.{args.dataset}")
    print("Type 'quit' to exit.\n")
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue
        answer = run_agent(question, verbose=not args.quiet)
        print(f"\nAgent: {answer}\n")


if __name__ == "__main__":
    main()
