import re
import unicodedata
from bs4 import BeautifulSoup


def make_slug(text: str) -> str:
    """Normalize text into a deduplication slug key."""
    # Strip leading sigils common in crypto/social media
    text = text.strip().lstrip("#$@!")
    # Unicode normalize
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    # Remove everything that isn't a letter, digit, or space
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Collapse whitespace to underscores
    text = re.sub(r"\s+", "_", text.strip())
    # Truncate to keep slugs manageable
    return text[:64]


def jaccard_similarity(a: str, b: str) -> float:
    """Word-level Jaccard similarity between two slugs (0.0 – 1.0)."""
    set_a = set(a.replace("_", " ").split())
    set_b = set(b.replace("_", " ").split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def find_matching_slug(new_slug: str, existing_slugs: list[str], threshold: float = 0.60) -> str | None:
    """
    Return the best matching existing slug if Jaccard similarity exceeds threshold,
    otherwise return None (meaning the new_slug is genuinely new).
    """
    best_slug = None
    best_score = 0.0
    for slug in existing_slugs:
        score = jaccard_similarity(new_slug, slug)
        if score > best_score:
            best_score = score
            best_slug = slug
    if best_score >= threshold:
        return best_slug
    return None


def strip_html(html: str) -> str:
    """Strip HTML tags and return plain text (used for 4chan comment bodies)."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    # Replace <br> and <p> with newlines before stripping
    for tag in soup.find_all(["br", "p"]):
        tag.replace_with("\n")
    return soup.get_text(separator=" ").strip()


def truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return re.sub(r"([" + re.escape(special) + r"])", r"\\\1", text)
