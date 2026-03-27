import io

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be set before importing pyplot
import matplotlib.pyplot as plt


def generate_score_chart(slug: str, history: list[tuple[str, float]]) -> io.BytesIO | None:
    """
    Generate a sparkline score chart for a trend.

    history: list of (timestamp_iso_str, score) tuples, oldest first.
    Returns a BytesIO PNG buffer, or None if fewer than 2 data points.
    """
    if len(history) < 2:
        return None

    labels = [h[0][11:16] for h in history]  # extract HH:MM from ISO timestamp
    scores = [h[1] for h in history]

    fig, ax = plt.subplots(figsize=(6, 2.2))

    ax.plot(range(len(scores)), scores,
            color="#00ff88", linewidth=2, marker="o", markersize=5, zorder=3)
    ax.fill_between(range(len(scores)), scores, alpha=0.15, color="#00ff88")

    ax.set_ylim(0, 1.05)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=7, color="#cccccc", rotation=30)
    ax.set_yticks([0, 0.3, 0.6, 1.0])
    ax.tick_params(axis="y", colors="#cccccc", labelsize=7)

    # Alert threshold line
    ax.axhline(y=0.30, color="#ff4444", linewidth=1, linestyle="--", alpha=0.7, label="Alert threshold")

    ax.set_title(f"📈  {slug.replace('_', ' ').title()}", fontsize=9,
                 color="white", pad=6)

    # Dark theme
    bg = "#1a1a2e"
    panel_bg = "#16213e"
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(panel_bg)
    for spine in ax.spines.values():
        spine.set_color("#333355")
    ax.grid(True, color="#222244", linewidth=0.5, linestyle="--")

    plt.tight_layout(pad=0.5)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=90, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return buf
