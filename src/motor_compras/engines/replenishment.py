from __future__ import annotations

from dataclasses import asdict

from motor_compras.models import AuditTrail, ProductSignal, Recommendation

ENGINE_VERSION = "0.1.0"
RULE_NAME = "reorder_point_v1"


def suggest_replenishment(signal: ProductSignal) -> tuple[Recommendation, AuditTrail]:
    consumo_ciclo = signal.venda_media_diaria * signal.lead_time_dias
    ponto_reposicao = int(round(consumo_ciclo + signal.estoque_seguranca))
    quantidade_sugerida = max(ponto_reposicao - signal.estoque_atual, 0)

    recommendation = Recommendation(
        sku=signal.sku,
        quantidade_sugerida=quantidade_sugerida,
        motivo=(
            f"Ponto de reposição={ponto_reposicao} (consumo ciclo={consumo_ciclo:.2f} + "
            f"estoque segurança={signal.estoque_seguranca})"
        ),
        engine_version=ENGINE_VERSION,
    )

    audit = AuditTrail.now(
        input_payload=asdict(signal),
        rule_name=RULE_NAME,
        output_payload=asdict(recommendation),
        engine_version=ENGINE_VERSION,
    )

    return recommendation, audit
