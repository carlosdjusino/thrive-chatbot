"""Integration tests: real embedding model + the cached sheet, indexed into a throwaway Chroma folder."""
import pytest

from thrive_chatbot import config, data
from thrive_chatbot.index import get_store, refresh_index
from thrive_chatbot.search import Searcher

pytestmark = pytest.mark.skipif(not config.CACHE_PATH.exists(), reason="needs data/cache/thrive.csv")


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    original = config.CHROMA_DIR
    config.CHROMA_DIR = tmp_path_factory.mktemp("chroma")
    articles = data.load_articles(refresh=False)
    stats = refresh_index(articles)
    yield Searcher(articles), articles, stats
    config.CHROMA_DIR = original


def test_index_counts_and_second_run_is_noop(env):
    _, articles, stats = env
    assert stats["added"] == len(articles)
    again = refresh_index(articles, store=get_store())
    assert again == {"added": 0, "updated": 0, "removed": 0, "unchanged": len(articles)}


def test_changed_and_removed_articles_are_picked_up(env):
    _, articles, _ = env
    edited = [a for a in articles]
    original_idea = edited[0].main_idea
    edited[0].main_idea = original_idea + " Edited."
    stats = refresh_index(edited[:-1], store=get_store())
    assert stats["updated"] == 1 and stats["removed"] == 1
    edited[0].main_idea = original_idea
    refresh_index(articles, store=get_store())  # restore


def test_topic_search_finds_expected_article(env):
    searcher, _, _ = env
    res = searcher.search("senior loneliness")
    assert res.status == "ok"
    assert any("Senior Cohousing" in h.article.title for h in res.hits)
    assert all(h.snippet for h in res.hits)


def test_category_filter_only_returns_that_area(env):
    searcher, _, _ = env
    res = searcher.search("programs for families", categories=["Education"])
    assert res.hits and all("Education" in h.article.categories for h in res.hits)


def test_gibberish_and_offtopic_give_no_match(env):
    searcher, _, _ = env
    for q in ("asdfgh qwerty", "what is the capital of France"):
        assert searcher.search(q).status == "no_match"


def test_empty_and_about_queries(env):
    searcher, _, _ = env
    assert searcher.search("   ").status == "empty"
    assert searcher.search("what is thrive?").status == "about"


def test_non_english_query_does_not_crash(env):
    searcher, _, _ = env
    res = searcher.search("vivienda asequible para familias")
    assert res.status in {"ok", "no_match"}


def test_article_without_link_is_still_returned(env):
    searcher, articles, _ = env
    no_link = next(a for a in articles if not a.link)
    res = searcher.search(no_link.title)
    hit = next(h for h in res.hits if h.article.id == no_link.id)
    assert hit.article.link == ""
