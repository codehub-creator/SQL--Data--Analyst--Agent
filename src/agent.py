import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from tools import get_schema, run_sql

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
TRACE_DIR = ROOT / "traces"
MODEL = os.getenv("GEMINI_MODEL")
MAX_STEPS = 6

client = genai.Client(http_options=types.HttpOptions(timeout=60000))  # 60s per call

# ---------------------------------------------------------------------------
# Prompt v1: the original minimal baseline. Kept unchanged so it can be rerun.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_V1 = """You are a data analyst agent. You answer questions about a SQLite database of e-commerce orders.

Rules:
1. Call get_schema first to see the tables and columns. Never guess column names.
2. Use run_sql to run SELECT queries. If a query returns an error, read it and fix the query.
3. Base your answer only on query results. Never invent numbers.
4. If the database cannot answer the question, say so clearly instead of guessing.
5. Give exact numbers (no abbreviations like "1.2M"). Write percentages with a % sign.
6. When you are ready, call final_answer with a short, direct answer. Set can_answer to false if the database cannot answer the question, otherwise true."""

# ---------------------------------------------------------------------------
# Prompt v2: written after reading the v1 failure traces.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_V2 = f"""You are a data analyst agent. You answer questions about a SQLite database of e-commerce orders. You have read-only access and at most {MAX_STEPS} steps, so work efficiently.

Rules:
1. Call get_schema exactly once, first. It lists every table and column that exists. Never guess column names, and do not look for tables or columns that get_schema did not list.
2. Use run_sql to run SELECT queries. If a query returns an error, read it and fix the query.
3. As soon as a query result answers the question, call final_answer immediately. Do not re-verify a result unless it is an error, empty, or implausible.
4. Base your answer only on query results. Never invent numbers.
5. If the question needs data that is not in the schema (for example a table or column that does not exist), do not keep searching. Call final_answer with can_answer=false and say what is missing.
6. You cannot modify data. If asked to delete, update, insert, create or drop anything, do not try. Call final_answer with can_answer=false and explain that you have read-only access.
7. Give exact numbers (no abbreviations like "1.2M"). Write percentages with a % sign.
8. Set can_answer=true only when you answered from query results."""

# Choose with the PROMPT_VERSION environment variable (default: v2)
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v2")
SYSTEM_PROMPT = SYSTEM_PROMPT_V1 if PROMPT_VERSION == "v1" else SYSTEM_PROMPT_V2

TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_schema",
            description="Get all tables with their columns, types, row counts and sample rows.",
        ),
        types.FunctionDeclaration(
            name="run_sql",
            description="Run one read-only SQLite SELECT query. Returns up to 50 rows or an error message.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING, description="A single SQLite SELECT query."
                    )
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="final_answer",
            description="Give the final answer to the user's question and stop.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "answer": types.Schema(
                        type=types.Type.STRING, description="The final answer with key numbers."
                    ),
                    "can_answer": types.Schema(
                        type=types.Type.BOOLEAN,
                        description="False if the database cannot answer the question, otherwise True.",
                    ),
                },
                required=["answer", "can_answer"],
            ),
        ),
    ]
)


def call_model(contents, config, max_attempts=5):
    """Call Gemini, retrying on rate limits and temporary server errors."""
    for attempt in range(max_attempts):
        try:
            return client.models.generate_content(
                model=MODEL, contents=contents, config=config
            )
        except errors.APIError as e:
            retryable = e.code in (429, 500, 503)
            if not retryable or attempt == max_attempts - 1:
                raise
            wait = 10 * (attempt + 1) if e.code == 429 else 3 * (attempt + 1)
            print(f"   [API error {e.code}, retrying in {wait}s]")
            time.sleep(wait)


def summarize(result):
    """Short text version of a tool result for printing."""
    if "schema" in result:
        return f"schema returned ({len(result['schema'])} chars)"
    if result.get("ok"):
        preview = json.dumps(result["rows"][:3], default=str)[:150]
        return f"ok, {result['row_count']} rows (truncated={result['truncated']}): {preview}"
    return f"ERROR: {result.get('error')}"


def save_trace(trace):
    """Save a trace file locally. The public demo turns this off with SAVE_TRACES=0."""
    if os.getenv("SAVE_TRACES", "1") != "1":
        return
    try:
        TRACE_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        (TRACE_DIR / f"trace_{stamp}.json").write_text(
            json.dumps(trace, indent=2, default=str), encoding="utf-8"
        )
    except OSError:
        pass  # never let logging break an answer


def run_agent(question, max_steps=MAX_STEPS, verbose=True):
    contents = [types.Content(role="user", parts=[types.Part(text=question)])]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[TOOLS],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    trace = {
        "question": question,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "started": datetime.now().isoformat(timespec="seconds"),
        "steps": [],
    }
    answer, status = None, "max_steps"
    can_answer = None
    in_tokens = out_tokens = 0
    t0 = time.time()

    if verbose:
        print(f"\nQUESTION: {question}")

    try:
        for step in range(1, max_steps + 1):
            response = call_model(contents, config)

            usage = response.usage_metadata
            if usage:
                in_tokens += usage.prompt_token_count or 0
                out_tokens += usage.candidates_token_count or 0

            if not response.candidates or not response.candidates[0].content:
                status = "error"
                trace["error"] = "Model returned no content (possibly blocked or empty)."
                break

            # Keep the model's turn exactly as returned, so the next call has full context
            contents.append(response.candidates[0].content)
            calls = response.function_calls or []

            # Model replied with plain text instead of a tool call
            if not calls:
                answer, status = response.text, "answered_text"
                trace["steps"].append({"step": step, "type": "text", "text": answer})
                if verbose:
                    print(f"[step {step}] (plain text answer)")
                break

            tool_parts, finished = [], False
            for call in calls:
                args = dict(call.args or {})

                if call.name == "final_answer":
                    answer, finished = args.get("answer", ""), True
                    can_answer = args.get("can_answer")
                    trace["steps"].append({"step": step, "tool": "final_answer", "input": args})
                    if verbose:
                        print(f"[step {step}] final_answer")
                    continue

                if call.name == "get_schema":
                    result = {"schema": get_schema()}
                elif call.name == "run_sql":
                    result = run_sql(args.get("query", ""))
                else:
                    result = {"ok": False, "error": f"Unknown tool: {call.name}"}

                trace["steps"].append(
                    {
                        "step": step,
                        "tool": call.name,
                        "input": args,
                        "result": {"schema": "(omitted)"} if "schema" in result else result,
                    }
                )
                if verbose:
                    detail = f": {args.get('query')}" if call.name == "run_sql" else ""
                    print(f"[step {step}] {call.name}{detail}")
                    print(f"          -> {summarize(result)}")

                tool_parts.append(
                    types.Part.from_function_response(name=call.name, response=result)
                )

            if finished:
                status = "answered"
                break
            contents.append(types.Content(role="user", parts=tool_parts))

    except Exception as e:
        status = "error"
        trace["error"] = f"{type(e).__name__}: {e}"[:500]

    seconds = round(time.time() - t0, 1)
    trace.update(
        {
            "status": status,
            "answer": answer,
            "can_answer": can_answer,
            "num_steps": len(trace["steps"]),
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "seconds": seconds,
        }
    )

    save_trace(trace)

    if verbose:
        print(f"ANSWER: {answer}")
        if "error" in trace:
            print(f"ERROR: {trace['error']}")
        print(
            f"(status={status}, steps={trace['num_steps']}, "
            f"tokens in/out={in_tokens}/{out_tokens}, {seconds}s)"
        )
    return trace


if __name__ == "__main__":
    if len(sys.argv) > 1:
        questions = [" ".join(sys.argv[1:])]
    else:
        questions = [
            "How many orders are in the database?",
            "Which 3 customer states have the most orders?",
            "What is the average age of our customers?",  # unanswerable on purpose
        ]
    for q in questions:
        run_agent(q)