# Motor de Compras Python — Grupo MB

Plataforma de Decisão Empresarial para compras e reposição no varejo multicanal.

## Norte arquitetural (obrigatório)

Este projeto segue a decisão `docs/07-decisao-arquitetural-decision-core.md`:

```text
Dados reais → PostgreSQL central → Motores determinísticos → Recomendação auditável → Agente IA explica e opera funções controladas
```

## Objetivo da fase atual

- Estruturar o núcleo determinístico de decisão.
- Expor recomendação e auditoria via FastAPI.
- Garantir testabilidade com pytest.

## Executando localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
uvicorn motor_compras.api.main:app --reload
```

## Endpoint inicial

`POST /decision/replenishment`

Payload de exemplo:

```json
{
  "sku": "TENIS-001",
  "estoque_atual": 5,
  "venda_media_diaria": 2.0,
  "lead_time_dias": 7,
  "estoque_seguranca": 4
}
```

Resposta: recomendação + trilha de auditoria (input, regra aplicada, output, versão do motor, timestamp UTC).
