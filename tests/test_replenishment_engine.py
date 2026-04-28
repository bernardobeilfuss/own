from motor_compras.engines.replenishment import ENGINE_VERSION, RULE_NAME, suggest_replenishment
from motor_compras.models import ProductSignal


def test_should_suggest_when_stock_below_reorder_point() -> None:
    signal = ProductSignal(
        sku="TENIS-001",
        estoque_atual=5,
        venda_media_diaria=2.0,
        lead_time_dias=7,
        estoque_seguranca=4,
    )

    recommendation, audit = suggest_replenishment(signal)

    assert recommendation.quantidade_sugerida == 13
    assert recommendation.engine_version == ENGINE_VERSION
    assert audit.rule_name == RULE_NAME


def test_should_not_suggest_when_stock_is_enough() -> None:
    signal = ProductSignal(
        sku="CAMISETA-010",
        estoque_atual=40,
        venda_media_diaria=1.5,
        lead_time_dias=7,
        estoque_seguranca=5,
    )

    recommendation, _ = suggest_replenishment(signal)

    assert recommendation.quantidade_sugerida == 0
