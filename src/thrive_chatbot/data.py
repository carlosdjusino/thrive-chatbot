"""Load the Thrive article sheet and turn it into clean Article records."""
import hashlib
import io
import re
from dataclasses import dataclass, field

import pandas as pd
import requests

from . import config


class SheetFormatError(ValueError):
    """Raised when required columns are missing from the sheet."""


@dataclass
class Article:
    id: str
    title: str
    authors: str
    link: str  # empty string when the article has no link
    main_idea: str
    problems: str
    solutions: str
    implement: str
    categories: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """The text we embed and keyword-search: every field the reviewers wrote."""
        parts = [
            self.title,
            self.main_idea,
            f"Problems: {self.problems}" if self.problems else "",
            f"Solutions: {self.solutions}" if self.solutions else "",
            f"How to apply: {self.implement}" if self.implement else "",
        ]
        return "\n".join(p for p in parts if p)

    @property
    def content_hash(self) -> str:
        meta = f"{self.link}|{self.authors}|{'; '.join(self.categories)}"
        return hashlib.sha1((self.text + meta).encode("utf-8")).hexdigest()


def is_empty(value) -> bool:
    return str(value if value is not None else "").strip().lower() in config.EMPTY_VALUES


def clean(value) -> str:
    return "" if is_empty(value) else re.sub(r"\s+", " ", str(value)).strip()


def _key(label: str) -> str:
    return re.sub(r"\s+", " ", str(label)).strip().lower()


def normalize_category(label: str) -> str:
    """'Community&Social (Case Studies)' -> 'Community & Social Connection'. Unknown labels pass through."""
    label = clean(label)
    if not label:
        return ""
    stripped = re.sub(r"\(.*?\)", "", label)
    key = re.sub(r"[^a-z]", "", stripped.lower())
    return config.CATEGORY_ALIASES.get(key, stripped.strip())


def split_categories(value) -> list[str]:
    seen: list[str] = []
    for part in re.split(r"[;\n]", clean(value)):
        cat = normalize_category(part)
        if cat and cat not in seen:
            seen.append(cat)
    return seen


def _find_header_row(df: pd.DataFrame) -> int:
    """Row index (in a header-less frame) that holds the real column names. Skips group-band rows."""
    wanted = {_key(h) for names in config.COLUMN_MAP.values() for h in names if not h.endswith("*")}
    for i in range(min(5, len(df))):
        cells = {_key(c) for c in df.iloc[i].tolist() if not pd.isna(c)}
        if len(cells & wanted) >= 3:
            return i
    raise SheetFormatError("Could not find a header row with the expected column names.")


def map_columns(headers: list[str]) -> dict[str, int]:
    """internal field -> column position, using COLUMN_MAP. Raises if required fields are missing."""
    keys = [_key(h) for h in headers]
    found: dict[str, int] = {}
    for fld, names in config.COLUMN_MAP.items():
        for name in names:
            hit = None
            for pos, k in enumerate(keys):
                if (name.endswith("*") and k.startswith(name[:-1])) or k == name:
                    hit = pos
                    break
            if hit is not None:
                found[fld] = hit
                break
    missing = [f for f in config.REQUIRED_FIELDS if f not in found]
    if missing:
        raise SheetFormatError(
            f"Sheet is missing required columns for: {', '.join(missing)}. "
            f"Update COLUMN_MAP in config.py. Headers seen: {[h for h in headers if str(h).strip()]}"
        )
    return found


def parse_csv_text(csv_text: str) -> list[Article]:
    raw = pd.read_csv(io.StringIO(csv_text), header=None, dtype=str, keep_default_na=False)
    header_row = _find_header_row(raw)
    cols = map_columns(raw.iloc[header_row].tolist())
    rows = raw.iloc[header_row + 1 :]

    def cell(row, fld: str) -> str:
        return clean(row.iloc[cols[fld]]) if fld in cols else ""

    articles: dict[str, Article] = {}
    for _, row in rows.iterrows():
        title = cell(row, "title")
        if not title or any(m in title.lower() for m in config.PLACEHOLDER_MARKERS):
            continue
        art = Article(
            id="",
            title=title,
            authors=cell(row, "authors"),
            link=cell(row, "link") if cell(row, "link").startswith("http") else "",
            main_idea=cell(row, "main_idea"),
            problems=cell(row, "problems"),
            solutions=cell(row, "solutions"),
            implement=cell(row, "implement"),
            categories=split_categories(row.iloc[cols["categories"]]) if "categories" in cols else [],
        )
        key = re.sub(r"\W+", " ", title.lower()).strip()
        art.id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        prev = articles.get(key)
        if prev is None:
            articles[key] = art
        else:
            # Same title listed twice: keep the fuller row, union the categories and link.
            keep, other = (art, prev) if len(art.text) > len(prev.text) else (prev, art)
            keep.categories = list(dict.fromkeys(keep.categories + other.categories))
            keep.link = keep.link or other.link
            articles[key] = keep
    return list(articles.values())


def fetch_csv_text(url: str = config.SHEET_URL, timeout: int = 30) -> str:
    """Download the sheet; on failure fall back to the cached copy so the app still works offline."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        config.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.CACHE_PATH.write_text(resp.text, encoding="utf-8")
        return resp.text
    except requests.RequestException:
        if config.CACHE_PATH.exists():
            return config.CACHE_PATH.read_text(encoding="utf-8")
        raise


def load_articles(refresh: bool = True) -> list[Article]:
    if refresh:
        text = fetch_csv_text()
    elif config.CACHE_PATH.exists():
        text = config.CACHE_PATH.read_text(encoding="utf-8")
    else:
        text = fetch_csv_text()
    return parse_csv_text(text)
