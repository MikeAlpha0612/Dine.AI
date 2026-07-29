"""Display formatting helpers for recommendations."""

from __future__ import annotations

from src.phase4_engine.schemas import Recommendation, RecommendationResult

MAX_EXPLANATION_DISPLAY_LENGTH = 280


def format_rating(rating: float) -> str:
    """Format rating to one decimal, or a fallback label for unrated."""
    if rating <= 0:
        return "New / Unrated"
    return f"{rating:.1f}"


def format_cost(cost: str | None) -> str:
    """Null-safe cost display."""
    if not cost or cost.strip().lower() in {"unknown", "none", "n/a"}:
        return "Cost not available"
    text = cost.strip()
    if text.startswith("₹"):
        return text
    # Numeric or range like "600" / "300-500"
    if text.replace("-", "").replace(",", "").isdigit() or "-" in text:
        return f"₹{text} for two"
    return text


def format_cuisine(cuisine: str | None) -> str:
    if not cuisine or cuisine.strip().lower() in {"n/a", "none", "null"}:
        return ""
    return cuisine.strip()


def truncate_explanation(
    text: str,
    *,
    max_length: int = MAX_EXPLANATION_DISPLAY_LENGTH,
) -> tuple[str, bool]:
    """Return (display_text, was_truncated)."""
    if len(text) <= max_length:
        return text, False
    return text[: max_length - 1].rstrip() + "…", True


def format_meta_line(rec: Recommendation) -> str:
    """Build 'Cuisine · ★ rating · cost' line, omitting empty parts."""
    parts: list[str] = []
    cuisine = format_cuisine(rec.cuisine)
    if cuisine:
        parts.append(cuisine)
    parts.append(f"★ {format_rating(rec.rating)}")
    parts.append(format_cost(rec.estimated_cost))
    if rec.area:
        parts.append(rec.area)
    return " · ".join(parts)


def format_recommendation_card(rec: Recommendation) -> str:
    """Plain-text card for CLI display."""
    preview, truncated = truncate_explanation(rec.explanation)
    lines = [
        f"#{rec.rank}  {rec.name}",
        f"   {format_meta_line(rec)}",
        f"   {preview}",
    ]
    if truncated:
        lines.append("   (explanation truncated)")
    return "\n".join(lines)


def format_result_summary(result: RecommendationResult) -> str:
    if result.is_empty:
        return result.message or "No restaurants match your preferences."
    parts = []
    if result.summary:
        parts.append(result.summary)
    if result.used_fallback:
        parts.append("AI ranking unavailable — showing top-rated matches.")
    if result.message and not result.is_empty:
        parts.append(result.message)
    return "\n".join(parts)
