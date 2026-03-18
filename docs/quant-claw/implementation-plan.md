# Quant Claw Implementation Plan

## 1. Project Goal

`quant-claw` is a multi-agent quantitative trading MVP focused on a narrow but executable path:

- market: crypto
- symbols: BTC / ETH
- runtime: paper trading / simulation first
- control flow: market event -> strategy proposal -> risk approval -> execution request -> fill -> portfolio update

The near-term goal is not a full production trading platform. It is a testable, reviewable execution framework that proves the core closed loop, isolates responsibilities, and provides a clean path toward backtest, sim, and live expansion.

## 2. Scope

### In scope

- Event-driven agent collaboration
- Funding-rate-based demo strategy path
- Risk gating before execution
- Execution through a paper broker adapter
- Position persistence / update loop
- API endpoints for health, positions, events, and simulation trigger
- Config-based team / strategy / runtime selection

### Out of scope for current MVP

- Real exchange execution
- Full OMS / EMS feature set
- Multi-account production reconciliation
- Advanced portfolio optimization
- Cross-venue smart routing
- Full compliance archive / approvals workflow
- Strategy marketplace or auto-generated alpha research

## 3. Business / System Roles

### Claw Quant Agent

Consumes market funding updates and transforms them into structured strategy proposals when signal thresholds are satisfied.

### Claw Risk Agent

Evaluates proposals against configured limits and emits approval or rejection decisions.

### Claw Trader Agent

Turns approved risk decisions into execution requests.

### Execution Gateway

Accepts execution requests, calls the paper broker, emits fill events, and persists order records.

### Portfolio Engine

Consumes fill events and updates current position state.

### Orchestrator

Wires all agents and services together, registers subscriptions, and ensures persistence hooks are active.

## 4. Core Workflow

1. Market data emits `market.funding.updated`
2. `ClawQuantAgent` creates `strategy.proposal.created`
3. `ClawRiskAgent` evaluates proposal
4. Risk emits either:
   - `risk.check.approved`
   - `risk.check.rejected`
5. `ClawTraderAgent` converts approval into `execution.order.requested`
6. `ExecutionGateway` executes in paper mode and emits `execution.order.filled`
7. `PortfolioEngine` converts fills into `portfolio.position.updated`

## 5. Risk Framework

Current implemented checks are intentionally minimal but structurally correct:

- proposal-level requested notional check
- approval / rejection event split
- leverage and slippage constraints included in decision payload
- reason codes attached to decisions

Current default example:

- max strategy notional: `30000`
- approved leverage: `1.5`
- max slippage: `10 bps`

Recommended next risk layers:

- symbol-level exposure limits
- team-level gross / net limits
- account-level drawdown circuit breaker
- venue health / market halt guardrails
- duplicate signal / duplicate order suppression
- live mode approval escalation

## 6. Delivery Phases

### Phase 1: MVP closed loop

Deliverables:
- working event bus
- quant / risk / trader agents
- paper execution gateway
- position update engine
- simulation test flow

### Phase 2: Architecture hardening

Deliverables:
- Redis event bus default
- stronger persistence model
- richer event schemas
- idempotency and replay support
- better observability and audit trail

### Phase 3: Strategy and environment expansion

Deliverables:
- multi-strategy team configs
- backtest / sim / paper environment separation
- exchange adapters
- richer portfolio and risk controls

### Phase 4: Production-readiness path

Deliverables:
- live trading guardrails
- on-call observability
- operations runbooks
- governance / approval workflows

## 7. Acceptance Criteria

The MVP can be considered valid when all of the following hold:

- a funding update can trigger a proposal automatically
- proposals can be deterministically approved or rejected by risk
- approved decisions generate execution requests
- execution requests generate fill events in paper mode
- fills update positions consistently
- key state can be queried via API
- demo flow test passes end-to-end

## 8. Risks and Controls

### Delivery risks

- architecture drifts before core loop is stable
- data contracts become inconsistent between agents
- risk logic stays too implicit
- paper assumptions leak into future live mode

### Control ideas

- freeze event schemas early
- keep every agent responsibility narrow
- enforce versioned config and event payloads
- maintain simulation tests for every new strategy path

## 9. Recommended Near-Term Outputs

The next useful project artifacts are:

1. technical architecture document
2. topic / payload protocol reference
3. MVP project skeleton explanation
4. staged backlog by sim -> paper -> live
