# Quant Claw MVP Skeleton

## 1. Purpose

This document maps the current repository into a practical MVP build skeleton so the project can move from concept review into implementation and extension.

## 2. Repository Layout

```text
quant-claw/
├── configs/
│   ├── base.yaml
│   ├── risk/
│   ├── strategies/
│   └── teams/
├── src/quant_claw/
│   ├── adapters/
│   ├── agents/
│   ├── api/
│   ├── apps/
│   ├── core/
│   ├── events/
│   ├── models/
│   └── services/
├── tests/
│   └── simulation/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## 3. What Each Module Means

### `configs/`

Configuration surface for runtime mode, team composition, strategy parameters, and risk controls.

### `adapters/`

External system boundaries.

Current examples:
- `paper_broker.py`
- `storage.py`

Future examples:
- exchange connectors
- market data connectors
- notification adapters

### `agents/`

Autonomous decision actors.

Current set:
- `base.py`
- `quant.py`
- `risk.py`
- `trader.py`

### `events/`

Transport layer abstraction.

Current set:
- `bus.py`
- `redis_bus.py`
- `topics.py`

### `models/`

Canonical business and transport schemas.

Current set includes:
- `event.py`
- `market.py`
- `proposal.py`
- `risk.py`
- `order.py`
- `position.py`

### `services/`

Process coordinators and side-effect executors.

Current set includes:
- `orchestrator.py`
- `execution_gateway.py`
- `portfolio_engine.py`
- `market_data_service.py`
- `audit_service.py`
- `persistence_service.py`

### `api/`

Operational query and control API.

### `apps/`

App entrypoints such as demo runners.

### `tests/simulation/`

End-to-end validation of the simulated event loop.

## 4. Current Base Abstractions

### Base Agent

`agents/base.py`

Provides:
- `agent_id`
- bus / logger injection
- common `emit()` helper
- required `start()` lifecycle

This is the minimum reusable abstraction for all agents.

### Event Schema

`models/event.py`

Provides the system-wide envelope used by the bus.

### Strategy Contract

Currently implicit in `StrategyProposal` plus the quant agent logic.

Recommended next step:
- introduce an explicit strategy interface, e.g. `strategies/base.py`
- separate signal generation from proposal serialization

### Risk Contract

Currently implicit in `ClawRiskAgent` plus `RiskDecision`.

Recommended next step:
- introduce pluggable risk policies
- separate limit evaluation from event emission

### Execution Gateway Contract

Currently implemented by `services/execution_gateway.py` around `PaperBroker`.

Recommended next step:
- formalize adapter interface for paper vs live broker implementations

## 5. Example Runtime Path

Using current configs:

- runtime mode: `paper`
- team: `btc-eth-focus`
- strategy: `funding_rate_arb`
- market symbols: `BTCUSDT`, `ETHUSDT`

This gives a concrete example team setup for demo and early testing.

## 6. Recommended Next Skeleton Additions

To make the MVP easier to extend, add these files next:

```text
src/quant_claw/
├── strategies/
│   ├── base.py
│   └── funding_rate_arb.py
├── risk/
│   ├── base.py
│   └── notional_limit.py
├── execution/
│   ├── broker_base.py
│   └── paper.py
└── schemas/
    └── versions.py
```

## 7. Suggested Build Order

1. freeze event and domain schemas
2. isolate strategy interface
3. isolate risk policy interface
4. formalize execution adapter interface
5. expand simulation tests
6. introduce backtest and paper/live environment switches

## 8. Definition of a Useful MVP Repository

This repository is MVP-ready when a new contributor can:

- install dependencies
- start local infra
- run the demo flow
- inspect generated positions and events
- understand where strategy, risk, and execution code should evolve

That is the right bar for the current stage: not “full production”, but “clear enough to build on without guessing.”
