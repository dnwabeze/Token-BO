import re


def suggest_tickers(name: str) -> list[str]:
    """
    Generate 3-5 potential Solana token ticker suggestions from a trend name.
    Returns a list like ['$PEPE', '$PEPECOIN', '$PC']
    """
    # Strip sigils and punctuation, uppercase
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", name).upper().strip()
    words = [w for w in clean.split() if w and len(w) > 1]

    if not words:
        return []

    suggestions: list[str] = []

    # 1. First word alone (up to 8 chars)
    if 2 <= len(words[0]) <= 8:
        suggestions.append(f"${words[0]}")

    # 2. First word truncated to 4 chars + last word truncated to 4 chars
    if len(words) >= 2:
        combo = (words[0][:4] + words[-1][:4])
        if 3 <= len(combo) <= 8 and combo not in [s[1:] for s in suggestions]:
            suggestions.append(f"${combo}")

    # 3. Acronym of all words (2-5 chars)
    acronym = "".join(w[0] for w in words)
    if 2 <= len(acronym) <= 5 and acronym not in [s[1:] for s in suggestions]:
        suggestions.append(f"${acronym}")

    # 4. Full compressed name (remove spaces, up to 6 chars)
    compressed = "".join(words)[:6]
    if len(compressed) >= 3 and compressed not in [s[1:] for s in suggestions]:
        suggestions.append(f"${compressed}")

    # 5. First word + "INU" suffix (meme coin convention)
    inu = words[0][:5] + "INU"
    if inu not in [s[1:] for s in suggestions]:
        suggestions.append(f"${inu}")

    return suggestions[:5]
