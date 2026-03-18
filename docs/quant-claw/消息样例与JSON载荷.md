# Quant Claw 消息样例与 JSON 载荷

## 1. 文档目的

本文档给出 `quant-claw` 当前主链路中各类事件的 JSON 样例，便于：

- 前后端或多模块联调
- 新开发者理解事件载荷
- 后续做 schema 固化与回放测试

说明：以下样例基于当前代码结构整理，属于**MVP 级协议样例**。

## 2. 通用事件信封

所有事件都通过统一的 `Event` 信封传输，格式如下：

```json
{
  "event_id": "evt_01HXYZEXAMPLE",
  "topic": "strategy.proposal.created",
  "ts": 1773790000000,
  "source": "claw_quant",
  "payload": {}
}
```

字段说明：

- `event_id`：事件唯一标识
- `topic`：事件主题
- `ts`：毫秒级时间戳
- `source`：事件来源
- `payload`：业务数据

## 3. 市场事件样例

### `market.funding.updated`

```json
{
  "event_id": "evt_market_001",
  "topic": "market.funding.updated",
  "ts": 1773790001000,
  "source": "market_data_service",
  "payload": {
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "funding_rate": 0.000164,
    "annualized_rate": 0.18,
    "next_funding_ts": 1773774600000
  }
}
```

## 4. 策略提案事件样例

### `strategy.proposal.created`

```json
{
  "event_id": "evt_prop_001",
  "topic": "strategy.proposal.created",
  "ts": 1773790002000,
  "source": "claw_quant",
  "payload": {
    "proposal_id": "prop_001",
    "signal_id": "sig_funding_demo",
    "team_id": "btc-eth-focus",
    "strategy_id": "funding_rate_arb",
    "symbol": "BTCUSDT",
    "action": "OPEN_PAIR",
    "legs": [
      {
        "venue": "binance_spot",
        "side": "BUY",
        "qty": 0.1
      },
      {
        "venue": "binance_perp",
        "side": "SELL",
        "qty": 0.1
      }
    ],
    "entry_constraints": {
      "max_slippage_bps": 10
    },
    "risk_context": {
      "requested_notional_usd": 7000
    },
    "status": "CREATED",
    "ts": 1773790002000,
    "note": "Annualized funding=18.00%"
  }
}
```

## 5. 风控通过事件样例

### `risk.check.approved`

```json
{
  "event_id": "evt_risk_approved_001",
  "topic": "risk.check.approved",
  "ts": 1773790003000,
  "source": "claw_risk",
  "payload": {
    "decision_id": "risk_001",
    "proposal_id": "prop_001",
    "status": "APPROVED",
    "approved_notional_usd": 7000,
    "max_leverage": 1.5,
    "constraints": {
      "max_slippage_bps": 10
    },
    "reason_codes": [
      "LIMIT_OK"
    ],
    "ts": 1773790003000
  }
}
```

## 6. 风控拒绝事件样例

### `risk.check.rejected`

```json
{
  "event_id": "evt_risk_rejected_001",
  "topic": "risk.check.rejected",
  "ts": 1773790003001,
  "source": "claw_risk",
  "payload": {
    "decision_id": "risk_002",
    "proposal_id": "prop_002",
    "status": "REJECTED",
    "approved_notional_usd": 0,
    "max_leverage": 1.0,
    "constraints": {},
    "reason_codes": [
      "STRATEGY_NOTIONAL_LIMIT_EXCEEDED"
    ],
    "ts": 1773790003001
  }
}
```

## 7. 执行请求事件样例

### `execution.order.requested`

```json
{
  "event_id": "evt_order_req_001",
  "topic": "execution.order.requested",
  "ts": 1773790004000,
  "source": "claw_trader",
  "payload": {
    "order_request_id": "ordreq_001",
    "proposal_id": "prop_001",
    "idempotency_key": "prop_001_1",
    "mode": "paper",
    "venue": "binance_perp",
    "symbol": "BTCUSDT",
    "side": "SELL",
    "order_type": "MARKET",
    "qty": 0.1,
    "price": null,
    "constraints": {
      "max_slippage_bps": 10
    },
    "status": "NEW",
    "ts": 1773790004000
  }
}
```

## 8. 成交事件样例

### `execution.order.filled`

```json
{
  "event_id": "evt_order_fill_001",
  "topic": "execution.order.filled",
  "ts": 1773790005000,
  "source": "execution_gateway",
  "payload": {
    "order_request_id": "ordreq_001",
    "proposal_id": "prop_001",
    "idempotency_key": "prop_001_1",
    "mode": "paper",
    "venue": "binance_perp",
    "symbol": "BTCUSDT",
    "side": "SELL",
    "order_type": "MARKET",
    "qty": 0.1,
    "price": null,
    "constraints": {
      "max_slippage_bps": 10
    },
    "status": "FILLED",
    "ts": 1773790004000,
    "fill_price": 70000.0,
    "filled_qty": 0.1,
    "fee": 2.8,
    "slippage_bps": 3.0
  }
}
```

## 9. 持仓更新事件样例

### `portfolio.position.updated`

```json
{
  "event_id": "evt_position_001",
  "topic": "portfolio.position.updated",
  "ts": 1773790006000,
  "source": "portfolio_engine",
  "payload": {
    "account_id": "sim_main",
    "strategy_id": "funding_rate_arb",
    "symbol": "BTCUSDT",
    "net_qty": -0.1,
    "gross_long_qty": 0.0,
    "gross_short_qty": 0.1,
    "avg_entry_price": 70000.0,
    "realized_pnl": -2.8,
    "margin_used": 4000,
    "ts": 1773790006000
  }
}
```

## 10. 建议后续补充

为了让这份样例文档更适合联调与测试，建议后续继续补：

- ETHUSDT 样例
- 风控边界值样例
- 执行失败 / 部分成交样例
- schema version 字段样例
- API 响应体样例
