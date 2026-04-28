from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI
from pydantic import BaseModel, Field

from motor_compras.engines.replenishment import suggest_replenishment
from motor_compras.models import ProductSignal

app = FastAPI(title="Motor de Compras - Grupo MB")


class ReplenishmentRequest(BaseModel):
    sku: str = Field(min_length=1)
    estoque_atual: int = Field(ge=0)
    venda_media_diaria: float = Field(ge=0)
    lead_time_dias: int = Field(ge=1)
    estoque_seguranca: int = Field(ge=0)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/decision/replenishment")
def replenishment_decision(payload: ReplenishmentRequest) -> dict:
    signal = ProductSignal(**payload.model_dump())
    recommendation, audit = suggest_replenishment(signal)

    return {
        "recommendation": asdict(recommendation),
        "audit": {
            **asdict(audit),
            "timestamp_utc": audit.timestamp_utc.isoformat(),
        },
    }
