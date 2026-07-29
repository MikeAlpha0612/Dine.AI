"""FastAPI REST layer for the Zomato-style frontend."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.phase5_app.service import AppService
from src.phase2_input.exceptions import InputValidationError

_service: Optional[AppService] = None


class RecommendRequest(BaseModel):
    location: str = Field(..., min_length=1)
    budget: Literal["low", "medium", "high"] = "medium"
    cuisine: Optional[str] = None
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    extra_preferences: Optional[str] = None


class RecommendationOut(BaseModel):
    rank: int
    name: str
    cuisine: str
    rating: float
    estimated_cost: str
    explanation: str
    area: Optional[str] = None
    restaurant_id: Optional[str] = None


class RecommendResponse(BaseModel):
    recommendations: list[RecommendationOut]
    summary: Optional[str] = None
    used_fallback: bool = False
    message: Optional[str] = None


def _env_max_rows() -> Optional[int]:
    raw = os.getenv("APP_MAX_ROWS", "").strip()
    return int(raw) if raw else None


def _env_use_llm() -> bool:
    return os.getenv("APP_USE_LLM", "1") not in {"0", "false", "False"}


def _ensure_ready() -> AppService:
    if _service is None:
        raise HTTPException(status_code=503, detail="Restaurant data is still loading.")
    if not _service.is_ready:
        detail = _service.load_error or "Restaurant data is still loading."
        raise HTTPException(status_code=503, detail=detail)
    return _service


def create_app(
    *,
    max_rows: Optional[int] = None,
    use_llm: Optional[bool] = None,
    skip_startup_load: bool = False,
) -> FastAPI:
    resolved_max_rows = max_rows if max_rows is not None else _env_max_rows()
    resolved_use_llm = _env_use_llm() if use_llm is None else use_llm

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _service
        if not skip_startup_load:
            _service = AppService(
                max_rows=resolved_max_rows,
                use_llm=resolved_use_llm,
                top_n=5,
            )
            try:
                _service.load()
            except Exception as exc:
                _service._load_error = str(exc)
                _service._ready = False
        yield

    app = FastAPI(
        title="Restaurant Recommendation API",
        version="0.2.0",
        lifespan=lifespan,
    )

    # CORS_ORIGINS=https://your-app.vercel.app,http://localhost:5173
    # Unset / "*" allows all origins (credentials disabled — browser-safe).
    raw_origins = os.getenv("CORS_ORIGINS", "*").strip()
    if raw_origins in {"", "*"}:
        allow_origins = ["*"]
        allow_credentials = False
    else:
        allow_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
        allow_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        ready = _service is not None and _service.is_ready
        payload = {
            "status": "ok" if ready else "loading",
            "restaurants": _service.restaurant_count if _service else 0,
            "cities": len(_service.get_locations()) if ready and _service else 0,
        }
        if _service is not None and _service.load_error:
            payload["status"] = "error"
            payload["error"] = _service.load_error
        return payload

    @app.get("/cities")
    def cities() -> dict:
        service = _ensure_ready()
        return {"cities": service.get_locations()}

    @app.get("/localities")
    def localities(
        location: str = Query(..., min_length=1),
        limit: int = Query(12, ge=1, le=50),
    ) -> dict:
        service = _ensure_ready()
        return {"location": location, "localities": service.localities(location, limit=limit)}

    @app.get("/cuisines")
    def cuisines(location: Optional[str] = None) -> dict:
        service = _ensure_ready()
        return {"cuisines": service.get_cuisines(location)}

    @app.get("/restaurants")
    def restaurants(
        location: str = Query(..., min_length=1),
        cuisine: Optional[str] = None,
        min_rating: float = Query(0.0, ge=0.0, le=5.0),
        budget: Optional[Literal["low", "medium", "high"]] = "medium",
        q: Optional[str] = None,
        sort: Literal["rating", "cost_asc", "cost_desc", "name"] = "rating",
        limit: int = Query(24, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict:
        service = _ensure_ready()
        try:
            return service.search_restaurants(
                location=location,
                cuisine=cuisine,
                min_rating=min_rating,
                budget=budget,
                query=q,
                limit=limit,
                offset=offset,
                sort=sort,
            )
        except InputValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/restaurants/{restaurant_id}")
    def restaurant_detail(restaurant_id: str) -> dict:
        service = _ensure_ready()
        restaurant = service.get_restaurant(restaurant_id)
        if restaurant is None:
            raise HTTPException(status_code=404, detail="Restaurant not found.")
        return restaurant

    @app.post("/recommend", response_model=RecommendResponse)
    def recommend(body: RecommendRequest) -> RecommendResponse:
        service = _ensure_ready()
        try:
            result = service.recommend(
                location=body.location,
                budget=body.budget,
                cuisine=body.cuisine,
                min_rating=body.min_rating,
                extra_preferences=body.extra_preferences,
            )
        except InputValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return RecommendResponse(
            recommendations=[
                RecommendationOut(
                    rank=r.rank,
                    name=r.name,
                    cuisine=r.cuisine,
                    rating=r.rating,
                    estimated_cost=r.estimated_cost,
                    explanation=r.explanation,
                    area=r.area,
                    restaurant_id=r.restaurant_id,
                )
                for r in result.recommendations
            ],
            summary=result.summary,
            used_fallback=result.used_fallback,
            message=result.message,
        )

    return app


app = create_app()
