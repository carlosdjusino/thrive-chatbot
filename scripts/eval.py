"""Score the search against data/test_questions.csv.

Positive questions pass if any expected title fragment appears in the top-5 results (recall@5).
Questions expecting NO_MATCH pass if the bot says it couldn't find anything or flags low confidence.

Run from the project root:  python scripts/eval.py
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thrive_chatbot import data  # noqa: E402
from thrive_chatbot.index import refresh_index  # noqa: E402
from thrive_chatbot.search import Searcher  # noqa: E402


def main() -> int:
    articles = data.load_articles(refresh=False)
    refresh_index(articles)
    searcher = Searcher(articles)

    rows = list(csv.DictReader(open(ROOT / "data" / "test_questions.csv", encoding="utf-8")))
    pos_pass = pos_total = neg_pass = neg_total = 0
    for row in rows:
        res = searcher.search(row["question"])
        titles = [h.article.title.lower() for h in res.hits]
        if row["expected"] == "NO_MATCH":
            neg_total += 1
            ok = res.status == "no_match" or res.low_confidence  # a loosely-related warning also counts
            neg_pass += ok
        else:
            pos_total += 1
            wanted = [w.lower() for w in row["expected"].split("|")]
            ok = any(w in t for w in wanted for t in titles)
            pos_pass += ok
        shown = res.status if res.status != "ok" else " / ".join(h.article.title[:45] for h in res.hits[:3])
        print(f"{'PASS' if ok else 'FAIL'}  {row['question'][:55]:55}  -> {shown}")

    print(f"\nrecall@5: {pos_pass}/{pos_total} = {pos_pass / max(pos_total, 1):.0%}")
    print(f"correct 'no match': {neg_pass}/{neg_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
