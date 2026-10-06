"""Usage statistics with Pandas + NumPy, charts with Matplotlib (US-08).

Plain Python (no Django): the view passes in a list of dicts, one per translation,
and gets back numbers, tables and ready-to-embed PNG charts.

Libraries used here:
  - NumPy: mean / median / percentile of text lengths
  - Pandas: DataFrame, groupby, value_counts, date ranges, reindex
  - Matplotlib: bar and line charts rendered to PNG in memory
"""
import base64
import io
from datetime import date, timedelta

import matplotlib

matplotlib.use("Agg")  # draw to memory, no GUI window (required on a web server)
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402  (must come after matplotlib.use)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .languages import AUTO, get_language_name  # noqa: E402

TIME_ZONE = "Asia/Kolkata"
COLUMNS = ["created_at", "source_lang", "target_lang", "char_count", "engine", "origin", "was_auto_detected"]
MIN_ROWS_FOR_CHARTS = 2

# One single-series colour per theme (validated against the light and dark card surfaces)
THEMES = {
    "light": {"series": "#2a78d6", "text": "#52514e", "grid": "#e2e2df"},
    "dark":  {"series": "#3987e5", "text": "#c3c2b7", "grid": "#3a3a37"},
}


# ---------------------------------------------------------------------------
# Data preparation (Pandas)
# ---------------------------------------------------------------------------

def to_dataframe(records):
    """List of dicts -> DataFrame with extra columns: local date, readable language names, pair."""
    df = pd.DataFrame.from_records(records, columns=COLUMNS)
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True).dt.tz_convert(TIME_ZONE)
    df["day"] = df["created_at"].dt.date
    name = lambda code: "Unknown" if code == AUTO else get_language_name(code)  # noqa: E731
    df["source_name"] = df["source_lang"].map(name)
    df["target_name"] = df["target_lang"].map(name)
    df["pair"] = df["source_name"] + " → " + df["target_name"]
    return df


def top_pairs(df, n=5):
    """Most used language pairs: Series {pair: count}, biggest first."""
    return df["pair"].value_counts().head(n)


def daily_counts(df, days=14, today=None):
    """Translations per day for the last `days` days, including days with zero."""
    today = today or date.today()
    all_days = pd.date_range(end=today, periods=days, freq="D").date
    counts = df.groupby("day").size()
    return counts.reindex(all_days, fill_value=0)   # missing days -> 0


def target_share(df, n=5):
    """Percentage of translations per target language; the rest grouped as 'Other'."""
    counts = df["target_name"].value_counts()
    top = counts.head(n)
    other = counts.iloc[n:].sum()
    if other:
        top = pd.concat([top, pd.Series({"Other": other})])
    return (top / counts.sum() * 100).round(1)


def length_stats(df):
    """Text length statistics with NumPy."""
    lengths = df["char_count"].to_numpy()
    return {
        "mean": float(np.round(np.mean(lengths), 1)),
        "median": float(np.median(lengths)),
        "p90": float(np.round(np.percentile(lengths, 90), 1)),
        "max": int(np.max(lengths)),
        "total_chars": int(np.sum(lengths)),
    }


def headline_numbers(df):
    """Single numbers for the stat tiles."""
    return {
        "total": int(len(df)),
        "pairs": int(df["pair"].nunique()),
        "auto_pct": float(np.round(df["was_auto_detected"].mean() * 100, 1)),
        "busiest_day": df.groupby("day").size().idxmax(),
        "top_target": df["target_name"].mode().iloc[0],
    }


# ---------------------------------------------------------------------------
# Charts (Matplotlib)
# ---------------------------------------------------------------------------

def _style_axes(ax, theme):
    colours = THEMES[theme]
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(colours["grid"])
    ax.tick_params(colors=colours["text"], labelsize=9, length=0)


def _to_base64_png(fig):
    """Save the figure into memory (not a file) and return it as base64 text for an <img> tag."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=110, transparent=True, bbox_inches="tight")
    plt.close(fig)  # free memory: figures are not garbage-collected automatically
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def horizontal_bar_chart(series, theme, value_format="{:g}"):
    """Horizontal bars, biggest at the top, with the value written at the end of each bar."""
    colours = THEMES[theme]
    series = series.iloc[::-1]  # matplotlib draws the first bar at the bottom
    fig, ax = plt.subplots(figsize=(6, 0.5 * len(series) + 0.6))
    bars = ax.barh(series.index, series.values, height=0.6, color=colours["series"])
    ax.bar_label(bars, labels=[value_format.format(v) for v in series.values],
                 padding=4, color=colours["text"], fontsize=9)
    ax.xaxis.set_visible(False)
    ax.set_xlim(0, series.max() * 1.15)
    _style_axes(ax, theme)
    return _to_base64_png(fig)


def line_chart(series, theme):
    """Daily counts as a line with markers; x axis shows dates like '06 Oct'."""
    colours = THEMES[theme]
    fig, ax = plt.subplots(figsize=(6, 2.8))
    x = pd.to_datetime(pd.Index(series.index))
    ax.plot(x, series.values, color=colours["series"], linewidth=2, marker="o", markersize=5)
    ax.set_ylim(bottom=0, top=max(series.max() * 1.2, 1))
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.grid(axis="y", color=colours["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    _style_axes(ax, theme)
    return _to_base64_png(fig)


def _both_themes(draw, *args, **kwargs):
    return {theme: draw(*args, theme=theme, **kwargs) for theme in THEMES}


# ---------------------------------------------------------------------------
# Everything the statistics page needs
# ---------------------------------------------------------------------------

def build_report(records, today=None):
    """records -> dict for the template. Returns {"enough_data": False} when there is too little."""
    df = to_dataframe(records)
    if len(df) < MIN_ROWS_FOR_CHARTS:
        return {"enough_data": False, "total": int(len(df))}

    pairs = top_pairs(df)
    daily = daily_counts(df, today=today)
    share = target_share(df)
    return {
        "enough_data": True,
        "headline": headline_numbers(df),
        "lengths": length_stats(df),
        # (label, value) lists for the accessible data tables under each chart
        "pairs_table": list(pairs.items()),
        "daily_table": [(day, int(count)) for day, count in daily.items()],
        "share_table": list(share.items()),
        "charts": {
            "pairs": _both_themes(horizontal_bar_chart, pairs),
            "daily": _both_themes(line_chart, daily),
            "share": _both_themes(horizontal_bar_chart, share, value_format="{:g}%"),
        },
    }
