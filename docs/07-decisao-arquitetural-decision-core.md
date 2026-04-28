# Decisão Arquitetural 07 — Decision Core do Grupo MB

## Status
Aprovada e mandatória.

## Contexto
O Grupo MB está evoluindo de uma operação fortemente apoiada em relatórios pesados no Power BI para uma plataforma própria de decisão empresarial. O cenário é multicanal (lojas físicas, WhatsApp, redes sociais, e-commerce e futuros marketplaces), com necessidade de rastreabilidade operacional e consistência entre canais.

## Decisão
Este projeto **não é um chatbot** e **não é apenas uma migração visual do Power BI para Python**.

Este projeto é uma **Plataforma de Decisão Empresarial** com fluxo arquitetural obrigatório:

```text
Dados reais → PostgreSQL central → Motores determinísticos → Recomendação auditável → Agente IA explica e opera funções controladas
```

### Regras mandatórias
1. Todo insight relevante nasce de dados persistidos no PostgreSQL central.
2. Toda recomendação operacional crítica deve ser produzida por motor determinístico testável.
3. O agente de IA não substitui o motor: ele explica decisões e aciona funções controladas.
4. Auditoria é requisito de primeira classe: entrada, regra aplicada, saída e versão do motor.
5. APIs devem expor recomendações e trilhas de auditoria de forma explícita.

## Consequências
- Redução de acoplamento entre camada analítica e interface.
- Melhor governança sobre decisões de compra e reposição.
- Base técnica preparada para MCP e agentes com escopo controlado.

## Fora de escopo
- Chatbot genérico sem vínculo com motores de decisão.
- Orquestração de decisões por prompts sem trilha determinística.

