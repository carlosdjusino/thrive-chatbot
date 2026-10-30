"""Settings shared across the chatbot. Edit COLUMN_MAP when the sheet's headers change."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SHEET_ID = "1TjkmhejcFU4GbuEUvL8Oyx5m3yqu3-_0w_kFp4yIBVI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
CACHE_PATH = ROOT / "data" / "cache" / "thrive.csv"
CHROMA_DIR = ROOT / "chroma_db"
FEEDBACK_PATH = ROOT / "feedback.jsonl"

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION = "thrive_articles"

# Internal field -> accepted sheet headers (case-insensitive). A trailing "*" matches any header
# that starts with that text. The first matching header wins, so list the current name first.
COLUMN_MAP = {
    "link": ["link", "link to document in drive"],
    "title": ["title"],
    "authors": ["authors", "author(s)", "author"],
    "main_idea": ["mainidea", "main idea", "summary"],
    "problems": ["problems", "issues identified", "problems in cf identified"],
    "solutions": ["solutions", "solutions identified", "solutions for cf identified"],
    "categories": ["thrive", "thrive area(s)", "thrive area"],
    "implement": ["implement", "how can the thrive working group operationalize*"],
}
REQUIRED_FIELDS = ["title", "main_idea"]

# Canonical THRIVE areas, keyed by the label with punctuation, spaces and "(...)" removed.
CATEGORY_ALIASES = {
    "education": "Education",
    "healthcare": "Healthcare",
    "economicstability": "Economic Stability",
    "communitysocial": "Community & Social Connection",
    "communitysocialconnection": "Community & Social Connection",
    "livability": "Livability",
}

PLACEHOLDER_MARKERS = ("do not delete",)
EMPTY_VALUES = {"", "-", "n/a", "na", "none", "nan"}

TOP_K = 5
CANDIDATES = 20  # how many results each retriever contributes before merging
# Measured on the real index: on-topic questions score >= 0.53, clearly off-topic ones <= 0.22, and
# short real queries ("kids") can score ~0.33. Below MIN we say "no match"; below LOW_CONFIDENCE we
# still show results but warn that they are only loosely related.
MIN_SEMANTIC_SCORE = float(os.getenv("MIN_SEMANTIC_SCORE", "0.30"))
LOW_CONFIDENCE_SCORE = 0.50

USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
LLM_MODEL = os.getenv("LLM_MODEL", "")
