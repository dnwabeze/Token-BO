from models.trend import RawSignal, TrendItem, SourceName

# Composite score weights — must sum to 1.0
W_RAW = 0.35
W_VELOCITY = 0.35
W_CROSS_SOURCE = 0.30

# Cross-source bonus per additional source, capped at 0.75
CROSS_SOURCE_BONUS_PER = 0.25
CROSS_SOURCE_CAP = 0.75

# Per-source velocity multipliers — 4chan early signals deserve more weight
SOURCE_VELOCITY_MULTIPLIER: dict[SourceName, float] = {
    SourceName.FOURCHAN_BIZ: 1.8,   # 4chan /biz/ breaks things earliest
    SourceName.FOURCHAN_POL: 1.5,   # /pol/ also early but noisier
    SourceName.REDDIT:       1.0,
    SourceName.TWITTER:      1.2,
    SourceName.GOOGLE:       1.0,
}

# Per-source raw score multipliers
SOURCE_RAW_MULTIPLIER: dict[SourceName, float] = {
    SourceName.FOURCHAN_BIZ: 1.3,
    SourceName.FOURCHAN_POL: 1.1,
    SourceName.REDDIT:       1.0,
    SourceName.TWITTER:      1.4,   # Twitter trending = already big
    SourceName.GOOGLE:       1.0,
}


def compute_score(trend: TrendItem, previous_signals: dict[str, float] | None = None) -> TrendItem:
    """
    Compute and update composite_score on the TrendItem in place.

    previous_signals: mapping of source.value → previous cycle raw_score
    """
    if not trend.signals:
        trend.composite_score = 0.0
        return trend

    if previous_signals is None:
        previous_signals = {}

    # 1. Normalized raw score — weighted average across signals
    raw_total = 0.0
    raw_weight = 0.0
    for signal in trend.signals:
        mult = SOURCE_RAW_MULTIPLIER.get(signal.source, 1.0)
        raw_total += signal.raw_score * mult
        raw_weight += mult
    avg_raw = (raw_total / raw_weight) if raw_weight > 0 else 0.0
    trend.normalized_raw_score = min(avg_raw, 1.0)

    # 2. Velocity score — weighted average with per-source multipliers
    velocity_total = 0.0
    velocity_weight = 0.0
    for signal in trend.signals:
        prev = previous_signals.get(signal.source.value)
        if prev is None or prev <= 0:
            vel = 1.0  # first appearance = max novelty
        else:
            delta = (signal.raw_score - prev) / prev
            vel = max(min(delta, 2.0), -1.0)
            vel = (vel + 1.0) / 3.0  # shift to [0, 1]

        mult = SOURCE_VELOCITY_MULTIPLIER.get(signal.source, 1.0)
        velocity_total += vel * mult
        velocity_weight += mult

    avg_velocity = min((velocity_total / velocity_weight) if velocity_weight > 0 else 0.0, 1.0)
    trend.velocity_score = avg_velocity

    # 3. Cross-source bonus
    bonus = min((trend.source_count - 1) * CROSS_SOURCE_BONUS_PER, CROSS_SOURCE_CAP)
    trend.cross_source_bonus = bonus

    # 4. Composite
    trend.composite_score = (
        W_RAW * trend.normalized_raw_score +
        W_VELOCITY * avg_velocity +
        W_CROSS_SOURCE * bonus
    )

    return trend
