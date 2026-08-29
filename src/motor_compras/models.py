from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ProductSignal:
    sku: str
    estoque_atual: int
    venda_media_diaria: float
    lead_time_dias: int
    estoque_seguranca: int


@dataclass(frozen=True)
class Recommendation:
    sku: str
    quantidade_sugerida: int
    motivo: str
    engine_version: str


@dataclass(frozen=True)
class AuditTrail:
    timestamp_utc: datetime
    input_payload: dict
    rule_name: str
    output_payload: dict
    engine_version: str

    @staticmethod
    def now(
        input_payload: dict,
        rule_name: str,
        output_payload: dict,
        engine_version: str,
    ) -> "AuditTrail":
        return AuditTrail(
            timestamp_utc=datetime.now(timezone.utc),
            input_payload=input_payload,
            rule_name=rule_name,
            output_payload=output_payload,
            engine_version=engine_version,
        )
