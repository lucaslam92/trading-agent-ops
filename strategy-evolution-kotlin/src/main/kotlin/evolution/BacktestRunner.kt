package evolution

interface BacktestRunner {
    fun run(task: BacktestTask): BacktestResult
}

class ExistingBacktestEngine {
    fun run(
        strategyName: String,
        symbol: String,
        timeframe: String,
        start: java.time.LocalDateTime,
        end: java.time.LocalDateTime,
        params: StrategyParams
    ): BacktestResult {
        throw NotImplementedError("接入你现有回测系统: strategy=$strategyName symbol=$symbol timeframe=$timeframe start=$start end=$end params=$params")
    }
}

class ExistingBacktestRunner(
    private val engine: ExistingBacktestEngine
) : BacktestRunner {

    override fun run(task: BacktestTask): BacktestResult {
        return engine.run(
            strategyName = task.strategyName,
            symbol = task.symbol,
            timeframe = task.timeframe,
            start = task.start,
            end = task.end,
            params = task.params
        )
    }
}
