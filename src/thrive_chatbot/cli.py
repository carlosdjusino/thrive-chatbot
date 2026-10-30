"""Quick terminal check:  python -m thrive_chatbot.cli "resources for senior loneliness" [--refresh] [--area Healthcare]"""
import argparse

from . import data
from .index import refresh_index
from .search import Searcher


def build_searcher(refresh_sheet: bool = False) -> tuple[Searcher, dict]:
    articles = data.load_articles(refresh=refresh_sheet)
    stats = refresh_index(articles)
    return Searcher(articles), stats


def print_result(res) -> None:
    if res.status != "ok":
        print(f"[{res.status}] {res.message}")
        return
    if res.low_confidence:
        print(f"[low confidence] {res.message}")
    for n, h in enumerate(res.hits, 1):
        sim = f"{h.similarity:.2f}" if h.similarity is not None else "keyword only"
        print(f"{n}. {h.article.title}  ({', '.join(h.article.categories)})  [{sim}; {'+'.join(h.via)}]")
        print(f"   {h.article.link or 'link unavailable'}")
        print(f"   {h.matched_field}: {h.snippet}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("--refresh", action="store_true", help="re-download the sheet first")
    p.add_argument("--area", action="append", help="filter by THRIVE area (repeatable)")
    args = p.parse_args()
    searcher, stats = build_searcher(args.refresh)
    print(f"index: {stats}")
    print_result(searcher.search(args.query, categories=args.area))


if __name__ == "__main__":
    main()
