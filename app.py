import gzip
import shutil
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
load_dotenv()

st.set_page_config(page_title="SQL Analyst Agent", page_icon="📊", layout="wide")

# On Streamlit Community Cloud, settings live in st.secrets. Copy them into the
# environment so the rest of the code can keep using os.getenv.
try:
    for _k in ("GEMINI_API_KEY", "GEMINI_MODEL", "SESSION_LIMIT", "DAILY_LIMIT",
               "SAVE_TRACES", "PROMPT_VERSION"):
        if _k in st.secrets and _k not in os.environ:
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass  # no secrets file locally; .env is used instead

SESSION_LIMIT = int(os.getenv("SESSION_LIMIT", "10"))  # questions per visitor session
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "150"))     # questions per day, all visitors
DB_PATH = ROOT / "data" / "olist.db"
DB_GZ_PATH = DB_PATH.with_name("olist.db.gz")


@st.cache_resource
def ensure_database():
    """Unpack the compressed database on first start (the repo stores olist.db.gz)."""
    if not DB_PATH.exists() and DB_GZ_PATH.exists():
        with gzip.open(DB_GZ_PATH, "rb") as src, open(DB_PATH, "wb") as dst:
            shutil.copyfileobj(src, dst)
    return DB_PATH.exists()


if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
    st.error("No API key found. Set GEMINI_API_KEY in .env (locally) or in the app's Secrets.")
    st.stop()
if not ensure_database():
    st.error("Database not found. Run `python src/load_data.py` locally, or add data/olist.db.gz.")
    st.stop()

from agent import MODEL, MAX_STEPS, run_agent  # noqa: E402

EXAMPLES = [
    "Which 3 customer states have the most orders?",
    "What percentage of all orders have the status 'delivered'?",
    "What are the top 5 product categories by items sold (English names)?",
    "What is the average age of our customers?",
    "Delete all canceled orders from the database.",
]


@st.cache_resource
def usage_counter():
    return {"day": date.today(), "count": 0}


def daily_usage():
    u = usage_counter()
    if u["day"] != date.today():
        u["day"], u["count"] = date.today(), 0
    return u


def set_question(text):
    st.session_state.question = text


def render_steps(trace):
    for s in trace["steps"]:
        n, tool = s["step"], s.get("tool")
        if tool == "get_schema":
            st.markdown(f"**Step {n}** · read the database schema")
        elif tool == "run_sql":
            st.markdown(f"**Step {n}** · ran a SQL query")
            st.code(s["input"].get("query", ""), language="sql")
            res = s["result"]
            if res.get("ok"):
                st.dataframe(pd.DataFrame(res["rows"], columns=res["columns"]), hide_index=True)
                if res.get("truncated"):
                    st.caption("Showing the first 50 rows only.")
            else:
                st.error(f"Query error: {res.get('error')}")
        elif tool == "final_answer":
            st.markdown(f"**Step {n}** · gave the final answer")
        elif s.get("type") == "text":
            st.markdown(f"**Step {n}** · replied in plain text")


# ------------------------------- layout -------------------------------
st.title("📊 SQL Data Analyst Agent")
st.write(
    "Ask a question about a Brazilian e-commerce database in plain English. "
    "The agent reads the schema, writes SQL, runs it **read-only**, fixes its own errors, "
    "and shows every step."
)

with st.sidebar:
    st.header("Try an example")
    for ex in EXAMPLES:
        st.button(ex, on_click=set_question, args=(ex,), key=f"ex_{ex}")
    st.divider()
    st.caption(f"Model: {MODEL} · max {MAX_STEPS} steps per question")
    st.caption(
        "Data: Olist Brazilian E-Commerce Public Dataset (Kaggle, CC BY-NC-SA 4.0). "
        "Answers come from an LLM and can be wrong, so check the SQL."
    )
    st.caption("Questions are sent to Google's Gemini API (free tier). Please don't enter personal information.")

st.session_state.setdefault("used", 0)
question = st.text_input("Your question", key="question", placeholder="e.g. Which state has the most customers?")
ask = st.button("Ask", type="primary")

if ask and question.strip():
    if st.session_state.used >= SESSION_LIMIT:
        st.warning(f"You've reached the limit of {SESSION_LIMIT} questions for this session.")
    elif daily_usage()["count"] >= DAILY_LIMIT:
        st.warning("The demo has reached its daily question limit. Please try again tomorrow.")
    else:
        st.session_state.used += 1
        daily_usage()["count"] += 1
        with st.spinner("The agent is working..."):
            st.session_state.trace = run_agent(question.strip(), verbose=False)

trace = st.session_state.get("trace")
if trace:
    status = trace["status"]
    if status == "error":
        st.error("The model API returned an error (often rate limiting on the free tier). Please try again in a minute.")
    elif status == "max_steps":
        st.warning(
            f"The agent used all {MAX_STEPS} steps without giving a final answer. "
            "This is a known failure mode. See the steps below."
        )
    elif trace.get("can_answer") is False:
        st.info(f"**The agent says the database can't help with this:** {trace['answer']}")
    else:
        st.success(trace["answer"])

    st.caption(
        f"{trace['num_steps']} steps · {trace['input_tokens']:,} input / "
        f"{trace['output_tokens']:,} output tokens · {trace['seconds']}s"
    )
    with st.expander("Show the agent's steps", expanded=True):
        render_steps(trace)