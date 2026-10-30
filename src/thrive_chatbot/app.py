"""Streamlit interface.  Run from the project root:  streamlit run src/thrive_chatbot/app.py"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from thrive_chatbot import config, data  # noqa: E402
from thrive_chatbot.index import refresh_index  # noqa: E402
from thrive_chatbot.search import STARTERS, Searcher  # noqa: E402

AREAS = [
    "Education",
    "Healthcare",
    "Economic Stability",
    "Community & Social Connection",
    "Livability",
]

st.set_page_config(page_title="THRIVE Library Guide", page_icon="📚", layout="centered")


@st.cache_resource(show_spinner="Loading the library and search index...")
def load(refresh_sheet: bool = False):
    articles = data.load_articles(refresh=refresh_sheet)
    stats = refresh_index(articles)
    return Searcher(articles), len(articles), stats


def log_feedback(query: str, article_id: str, rating: str) -> None:
    with open(config.FEEDBACK_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "query": query, "article": article_id, "rating": rating}) + "\n")


with st.sidebar:
    st.header("Filters")
    areas = st.multiselect("THRIVE area", AREAS, placeholder="All areas")
    if st.button("Refresh data from sheet"):
        load.clear()
        searcher, total, stats = load(refresh_sheet=True)
        st.success(f"Updated: {stats}")

searcher, total, _ = load()

st.title("THRIVE Library Guide")
st.caption(f"Find resources in the THRIVE Central Florida literature review ({total} articles).")

if "query" not in st.session_state:
    st.session_state.query = ""

with st.form("search", clear_on_submit=False):
    typed = st.text_input("What topic are you looking for?", value=st.session_state.query,
                          placeholder="e.g. resources on senior loneliness")
    submitted = st.form_submit_button("Search")
if submitted:
    st.session_state.query = typed

st.write("Try one:")
cols = st.columns(2)
for n, starter in enumerate(STARTERS):
    if cols[n % 2].button(starter, key=f"starter{n}"):
        st.session_state.query = starter
        st.rerun()

query = st.session_state.query
if query:
    res = searcher.search(query, categories=areas or None)
    if res.status in ("about", "empty", "no_match"):
        st.info(res.message)
    else:
        if config.USE_LLM:
            from thrive_chatbot.answer import generate_answer

            with st.spinner("Writing a short answer from these articles..."):
                st.markdown(generate_answer(query, res.hits))
        if res.low_confidence:
            st.warning(res.message)
        st.subheader(f"{len(res.hits)} matching resources")
        for n, hit in enumerate(res.hits):
            a = hit.article
            with st.container(border=True):
                st.markdown(f"**[{a.title}]({a.link})**" if a.link else f"**{a.title}** · _link unavailable_")
                meta = " · ".join(x for x in [a.authors, ", ".join(a.categories)] if x)
                if meta:
                    st.caption(meta)
                st.markdown(f"**Why it matched** ({hit.matched_field}): {hit.snippet}")
                with st.expander("Full summary"):
                    st.write(a.main_idea)
                    for label, text in (("Problems", a.problems), ("Solutions", a.solutions), ("How to apply", a.implement)):
                        if text:
                            st.markdown(f"**{label}:** {text}")
                up, down, _ = st.columns([1, 1, 6])
                fb_key = f"fb-{query}-{a.id}"
                if st.session_state.get(fb_key):
                    st.caption("Thanks for the feedback!")
                elif up.button("👍", key=f"up{n}"):
                    log_feedback(query, a.id, "up")
                    st.session_state[fb_key] = True
                    st.rerun()
                elif down.button("👎", key=f"down{n}"):
                    log_feedback(query, a.id, "down")
                    st.session_state[fb_key] = True
                    st.rerun()
