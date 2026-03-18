# Quant Claw Technical Architecture

## 1. Architecture Summary

`quant-claw` is structured as an event-driven multi-agent system. The core design principle is separation of concern by decision stage rather than by monolithic service.

Main layers:

- `agents/`: decision-making actors
- `services/`: orchestration, execution, portfolio, persistence
- `events/`: bus abstraction and topic registry
- `models/`: canonical payload models
- `configs/`: runtime, strategy, risk, and team configuration
- `api/`: operational read/query and simulation trigger endpoints

## 2. Current Service Breakdown

### Agents

- `ClawQuantAgent`
  - subscribes to `market.funding.updated`
  - emits `strategy.proposal.created`

- `ClawRiskAgent`
  - subscribes to `strategy.proposal.created`
  - emits `risk.check.approved` or `risk.check.rejected`

- `ClawTraderAgent`
  - subscribes to `risk.check.approved`
  - emits `execution.order.requested`

### Services

- `Orchestrator`
  - instantiates agents
  - registers subscriptions
  - connects persistence hooks and services

- `ExecutionGateway`
  - subscribes to execution requests via orchestrator wiring
  - calls `PaperBroker`
  - emits `execution.order.filled`

- `PortfolioEngine`
  - subscribes to `execution.order.filled`
  - emits `portfolio.position.updated`

- `PersistenceService`
  - stores events and business entities

## 3. Event Topics

Current implemented topics:

- `market.funding.updated`
- `strategy.proposal.created`
- `risk.check.approved`
- `risk.check.rejected`
- `execution.order.requested`
- `execution.order.filled`
- `portfolio.position.updated`

## 4. Event Flow

```text
MarketDataService / simulator
    -> market.funding.updated
        -> ClawQuantAgent
            -> strategy.proposal.created
                -> ClawRiskAgent
                    -> risk.check.approved
                        -> ClawTraderAgent
                            -> execution.order.requested
                                -> ExecutionGateway
                                    -> execution.order.filled
                                        -> PortfolioEngine
                                            -> portfolio.position.updated
```

Rejected branch:

```text
strategy.proposal.created
    -> ClawRiskAgent
        -> risk.check.rejected
```

## 5. Canonical Models

### Event

Base transport envelope:

- `event_id`
- `topic`
- `ts`
- `source`
- `payload`

This is the common wrapper for all inter-agent communication.

### StrategyProposal

Purpose: describe a strategy-originated executable idea before risk approval.

Main fields:

- `proposal_id`
- `signal_id`
- `team_id`
- `strategy_id`
- `symbol`
- `action`
- `legs[]`
- `entry_constraints`
- `risk_context`
- `status`
- `ts`
- `note`

### RiskDecision

Purpose: convert a proposal into a governed approval decision.

Main fields:

- `decision_id`
- `proposal_id`
- `status`
- `approved_notional_usd`
- `max_leverage`
- `constraints`
- `reason_codes`
- `ts`

### ExecutionOrder

Purpose: concrete order request generated from an approved decision.

Main fields:

- `order_request_id`
- `proposal_id`
- `idempotency_key`
- `mode`
- `venue`
- `symbol`
- `side`
- `order_type`
- `qty`
- `price`
- `constraints`
- `status`
- `ts`

## 6. Config Topology

### Base runtime config

`configs/base.yaml`

Defines:
- app metadata
- runtime mode
- default team
- bus backend
- database URL
- logging level

### Team config

`configs/teams/btc-eth-focus.yaml`

Defines:
- team id / name
- market
- symbols
- enabled agents
- enabled strategies

### Risk / strategy configs

Located under:
- `configs/risk/`
- `configs/strategies/`

These should become the main knobs for rollout without code changes.

## 7. Environment Isolation

Recommended environment model:

### Backtest

- offline historical data
- deterministic replay
- no real broker adapter
- full event capture for reproducibility

### Simulation / Demo

- synthetic or replayed market events
- paper broker execution
- local Redis/Postgres optional
- used for integration verification

### Paper Trading

- real market feed
- fake capital / no real order submission
- production-like controls and observability

### Live Trading

- real exchange adapters
- stricter risk, kill switch, operator approval, audit

## 8. Topic Naming Guidance

Current topic style is good and should be preserved:

`domain.entity.action`

Examples:
- `market.funding.updated`
- `strategy.proposal.created`
- `execution.order.filled`

Suggested additions should follow the same convention, e.g.:
- `market.price.tick`
- `risk.limit.triggered`
- `execution.order.cancel_requested`
- `portfolio.pnl.updated`

## 9. Schema Governance Guidance

To prevent drift as the system grows:

- keep Pydantic models as canonical contracts
- avoid anonymous dict payloads outside envelope construction boundaries
- version schemas when breaking changes appear
- require replay tests when schema or topic semantics change

## 10. Deployment Topology

Current local topology:

- app runtime in Python
- Redis for bus backend
- Postgres for persistence
- FastAPI for operational endpoints

Suggested production-shaped topology later:

- agent runtime container(s)
- Redis / stream backbone
- Postgres primary store
- metrics / logs sink
- operator dashboard / admin API

## 11. Gaps to Close Next

Highest-value architecture gaps:

1. explicit market data service contract
2. richer order lifecycle states
3. replay / idempotency strategy
4. formal API contract documentation
5. live-mode exchange adapter boundary
6. team-level and account-level risk aggregation
