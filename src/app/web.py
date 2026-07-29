"""Streamlit web UI for restaurant recommendations."""

from __future__ import annotations

import os
from typing import Optional

import streamlit as st

from src.app.service import AppService
from src.app.ui.forms import BUDGET_OPTIONS, validate_form
from src.app.ui.results import format_meta_line, truncate_explanation
from src.input.exceptions import InputValidationError


@st.cache_resource(show_spinner=False)
def get_app_service(
    max_rows: Optional[int] = None,
    use_llm: bool = True,
) -> AppService:
    service = AppService(max_rows=max_rows, use_llm=use_llm, top_n=5)
    service.load()
    return service


def _render_recommendation_cards(result) -> None:
    if result.summary:
        st.info(result.summary)

    if result.used_fallback:
        st.warning("AI ranking unavailable — showing top-rated matches from the dataset.")

    if result.message and not result.is_empty:
        st.caption(result.message)

    for rec in result.recommendations:
        with st.container(border=True):
            st.markdown(f"### #{rec.rank}  {rec.name}")
            st.caption(format_meta_line(rec))

            preview, truncated = truncate_explanation(rec.explanation)
            st.write(preview)
            if truncated:
                with st.expander("Read more"):
                    st.write(rec.explanation)


def main() -> None:
    st.set_page_config(
        page_title="Restaurant Recommendations",
        page_icon="🍽️",
        layout="centered",
    )

    st.title("Restaurant Recommendations")
    st.caption("AI-powered suggestions across cities in India")

    max_rows_env = os.getenv("APP_MAX_ROWS")
    max_rows = int(max_rows_env) if max_rows_env else None
    use_llm = os.getenv("APP_USE_LLM", "1") not in {"0", "false", "False"}

    with st.spinner("Loading restaurant data across India…"):
        try:
            service = get_app_service(max_rows=max_rows, use_llm=use_llm)
        except Exception as exc:
            st.error(f"Failed to load dataset: {exc}")
            st.stop()

    locations = service.get_locations()
    st.sidebar.success(
        f"{service.restaurant_count:,} restaurants · {len(locations):,} cities"
    )
    if not use_llm:
        st.sidebar.info("Running without LLM (fallback ranking)")

    preferred = [
        "Bangalore",
        "New Delhi",
        "Mumbai",
        "Hyderabad",
        "Chennai",
        "Pune",
        "Kolkata",
        "Jaipur",
        "Ahmedabad",
        "Lucknow",
        "Chandigarh",
        "Goa",
    ]
    ordered = [c for c in preferred if c in locations] + [
        c for c in locations if c not in preferred
    ]
    default_index = ordered.index("Bangalore") if "Bangalore" in ordered else 0

    with st.form("preferences_form", clear_on_submit=False):
        if ordered:
            location = st.selectbox(
                "Location (type to search any city)",
                options=ordered,
                index=default_index,
                help="Nationwide coverage — type to search cities across India.",
            )
        else:
            location = st.text_input(
                "Location",
                value="Bangalore",
                placeholder="e.g. Bangalore, Delhi, Mumbai, Jaipur",
            )
        budget = st.selectbox("Budget", options=list(BUDGET_OPTIONS), index=1)
        cuisine = st.text_input(
            "Cuisine (optional)",
            value="",
            placeholder="e.g. Italian, Chinese",
        )
        min_rating = st.slider("Minimum rating", 0.0, 5.0, 0.0, 0.1)
        extra = st.text_area(
            "Extra preferences (optional)",
            value="",
            placeholder="e.g. family-friendly, quick service",
            max_chars=500,
        )
        submitted = st.form_submit_button(
            "Get recommendations",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        st.markdown(
            "Enter your preferences and click **Get recommendations** "
            "to see ranked restaurants with explanations."
        )
        return

    payload, error = validate_form(
        location=location,
        budget=budget,
        cuisine=cuisine or None,
        min_rating=min_rating,
        extra_preferences=extra or None,
    )
    if error:
        st.error(error)
        return

    with st.spinner("Generating recommendations…"):
        try:
            assert payload is not None
            result = service.recommend(
                location=payload["location"],
                budget=payload["budget"],
                cuisine=payload.get("cuisine"),
                min_rating=payload.get("min_rating", 0.0),
                extra_preferences=payload.get("extra_preferences"),
            )
        except InputValidationError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")
            return

    if result.is_empty:
        st.warning(result.message or "No restaurants match your preferences.")
        st.markdown(
            "Try relaxing filters: remove cuisine, lower minimum rating, "
            "or choose a different budget."
        )
        return

    st.subheader(f"Top {len(result.recommendations)} recommendations")
    _render_recommendation_cards(result)


if __name__ == "__main__":
    main()
