# Python Bridge Design

## Goal
Wire the Kotlin Strategy Evolution Engine to the existing Python backtest system without rewriting the backtest core.

## Proposed flow
1. Kotlin generates `BacktestTask`
2. Kotlin bridge writes a temporary JSON config file
3. Kotlin invokes Python `runner/run_backtest.py --config <temp_config>`
4. Python prints standardized metrics
5. Kotlin parses stdout into `BacktestResult`

## Required Python contract
The Python side should support:
- receiving strategy parameters through config JSON
- printing metrics fields in stable machine-readable format
- optional export of trades JSON for `TradeRecord`

## Suggested next implementation
- add one Python helper script, for example `scripts/run_backtest_bridge.py`
- input: config path or JSON task payload
- output: JSON with `metrics` and optional `trades`

## Current Kotlin status
`PythonBridgeBacktestEngine` exists as a stub and is the intended integration point.
