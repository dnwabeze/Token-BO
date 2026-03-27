from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def get_sentiment(text: str) -> float:
    """
    Returns a compound sentiment score from -1.0 (very negative) to +1.0 (very positive).
    Scores near 0 are neutral.
    """
    if not text:
        return 0.0
    return _analyzer.polarity_scores(text)["compound"]


def sentiment_label(score: float) -> str:
    if score >= 0.05:
        return "🟢 Positive"
    elif score <= -0.05:
        return "🔴 Negative"
    else:
        return "⚪ Neutral"
