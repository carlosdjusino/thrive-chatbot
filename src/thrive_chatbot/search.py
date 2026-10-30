"""Hybrid retrieval: semantic (embeddings) + keyword (BM25), merged with reciprocal rank fusion."""
import re
from dataclasses import dataclass, field

import numpy as np
from rank_bm25 import BM25Okapi

from . import config
from .data import Article
from .index import get_embeddings, get_store

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "with", "about", "are", "is", "there",
    "what", "which", "who", "how", "do", "does", "i", "we", "you", "me", "my", "can", "any", "some",
    "out", "resources", "resource", "articles", "article", "papers", "paper", "information", "info",
    "find", "show", "give", "need", "want", "looking", "help", "please",
}
ABOUT_PATTERN = re.compile(
    r"^\s*(hi|hello|hey|help|what is (the )?thrive|what is this|how (do|does) (i|this|it)|how to use|"
    r"what can you do|who are you)\b",
    re.I,
)
ABOUT_TEXT = (
    "THRIVE Central Florida is a collaboration between the Central Florida Foundation and Florida "
    "Community Innovation. This library holds reviewed policy articles and case studies in five areas: "
    "Education, Healthcare, Economic Stability, Community & Social Connection, and Livability. "
    "Ask for a topic, like \"resources on senior loneliness\", or filter by area."
)
STARTERS = [
    "What resources are out there for affordable housing?",
    "Programs that help children get ready for kindergarten",
    "How can nonprofits improve civic engagement?",
    "Mental health services in Central Florida",
]
FIELD_LABELS = {
    "main_idea": "Main idea",
    "problems": "Problems",
    "solutions": "Solutions",
    "implement": "How to apply",
}


@dataclass
class Hit:
    article: Article
    similarity: float | None  # cosine similarity to the query, None if only keyword-matched
    matched_field: str
    snippet: str
    via: list[str] = field(default_factory=list)  # "semantic", "keyword"


@dataclass
class SearchResult:
    status: str  # ok | no_match | empty | about
    hits: list[Hit]
    message: str = ""
    low_confidence: bool = False  # results exist but are only loosely related to the question


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and len(t) > 1]


def split_chunks(text: str) -> list[str]:
    """Reviewer fields use ' + ', newlines, and sentences. Split so we can point at the best piece."""
    parts = re.split(r"\s\+\s|\n|(?<=[.!?])\s+(?=[A-Z])", text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


class Searcher:
    def __init__(self, articles: list[Article], store=None):
        self.articles = {a.id: a for a in articles}
        self.store = store or get_store()
        ids = list(self.articles)
        self._bm25_ids = ids
        self._bm25 = BM25Okapi([tokenize(self.articles[i].text) or ["_"] for i in ids])

    # ---- retrieval -------------------------------------------------------------------------
    def _semantic(self, query: str, fetch: int) -> list[tuple[str, float]]:
        res = self.store.similarity_search_with_score(query, k=min(fetch, len(self.articles)))
        out = []
        for doc, dist in res:
            art_id = next((i for i, a in self.articles.items() if a.title == doc.metadata["title"]), None)
            if art_id:
                out.append((art_id, 1.0 - float(dist)))  # cosine distance -> similarity
        return out

    def _keyword(self, query: str, fetch: int) -> list[tuple[str, float]]:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        order = np.argsort(scores)[::-1][:fetch]
        return [(self._bm25_ids[i], float(scores[i])) for i in order if scores[i] > 0]

    def _explain(self, article: Article, query_vec: np.ndarray) -> tuple[str, str]:
        """Pick the reviewer-written sentence that is closest in meaning to the question."""
        candidates = []
        for key, label in FIELD_LABELS.items():
            for chunk in split_chunks(getattr(article, key)):
                candidates.append((label, chunk))
        if not candidates:
            return FIELD_LABELS["main_idea"], article.main_idea
        vecs = np.array(get_embeddings().embed_documents([c for _, c in candidates]))
        best = int(np.argmax(vecs @ query_vec))
        return candidates[best]

    # ---- public API ------------------------------------------------------------------------
    def search(self, query: str, categories: list[str] | None = None, k: int = config.TOP_K) -> SearchResult:
        query = (query or "").strip()
        if not query:
            return SearchResult("empty", [], "Type a topic to search the library.")
        if ABOUT_PATTERN.match(query):
            return SearchResult("about", [], ABOUT_TEXT)

        fetch = len(self.articles) if categories else config.CANDIDATES
        sem = self._semantic(query, fetch)
        kw = self._keyword(query, fetch)
        if categories:
            allowed = {i for i, a in self.articles.items() if set(categories) & set(a.categories)}
            sem = [(i, s) for i, s in sem if i in allowed]
            kw = [(i, s) for i, s in kw if i in allowed]

        sim = dict(sem)
        kw_rank = {i: r for r, (i, _) in enumerate(kw)}
        best_sim = max(sim.values(), default=0.0)
        if best_sim < config.MIN_SEMANTIC_SCORE:
            return SearchResult(
                "no_match",
                [],
                "I couldn't find that in the library. Try a different topic or browse by area "
                "(Education, Healthcare, Economic Stability, Community & Social Connection, Livability).",
            )

        fused: dict[str, float] = {}
        for rank, (i, _) in enumerate(sem[: config.CANDIDATES]):
            fused[i] = fused.get(i, 0) + 1 / (60 + rank)
        for rank, (i, _) in enumerate(kw[: config.CANDIDATES]):
            fused[i] = fused.get(i, 0) + 1 / (60 + rank)

        # Keep an article if it is meaningfully similar, or a top keyword hit that is not wildly off-topic.
        keep = [
            i for i in fused
            if sim.get(i, 0.0) >= config.MIN_SEMANTIC_SCORE
            or (kw_rank.get(i, 99) < 3 and sim.get(i, 0.0) >= config.MIN_SEMANTIC_SCORE * 0.6)
        ]
        ranked = sorted(keep, key=lambda i: fused[i], reverse=True)[:k]
        if not ranked:
            return SearchResult("no_match", [], "I couldn't find that in the library.")

        qvec = np.array(get_embeddings().embed_query(query))
        hits = []
        for i in ranked:
            art = self.articles[i]
            label, snippet = self._explain(art, qvec)
            via = (["semantic"] if sim.get(i, 0) >= config.MIN_SEMANTIC_SCORE else []) + (
                ["keyword"] if i in kw_rank else []
            )
            hits.append(Hit(art, sim.get(i), label, snippet, via))
        low = best_sim < config.LOW_CONFIDENCE_SCORE
        message = "These are only loosely related to your question. Try rewording it or pick an area." if low else ""
        return SearchResult("ok", hits, message, low_confidence=low)
