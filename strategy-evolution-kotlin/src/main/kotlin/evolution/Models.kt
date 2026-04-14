package evolution

import java.time.Duration
import java.time.LocalDateTime

data class StrategySpec(
    val strategyName: String,
    val randomParamFactory: (java.util.Random) -> StrategyParams
)

data class StrategyParams(
    val maWindow: Int,
    val adxWindow: Int,
    val adxThreshold: Double,
    val swingWindow: Int,
    val retestToleranceAtr: Double,
    val stopAtrMultiplier: Double,
    val trailingAtrMultiplier: Double,
    val minHoldingBars: Int
)

data class BacktestTask(
    val strategyName: String,
    val params: StrategyParams,
    val symbol: String,
    val timeframe: String,
    val start: LocalDateTime,
    val end: LocalDateTime
)

data class Metrics(
    val totalReturn: Double,
    val annualReturn: Double,
    val maxDrawdown: Double,
    val sharpe: Double,
    val calmar: Double,
    val totalTrades: Int,
    val winRate: Double,
    val avgWin: Double,
    val avgLoss: Double,
    val profitFactor: Double,
    val grossPnl: Double,
    val netPnl: Double,
    val totalFee: Double,
    val avgHoldingTime: Duration,
    val longPnl: Double,
    val shortPnl: Double
) {
    val feeRatio: Double
        get() = if (grossPnl <= 0.0) Double.POSITIVE_INFINITY else totalFee / grossPnl
}

data class TradeRecord(
    val entryTime: LocalDateTime,
    val exitTime: LocalDateTime,
    val side: String,
    val entryPrice: Double,
    val exitPrice: Double,
    val pnl: Double,
    val fee: Double
)

data class BacktestResult(
    val task: BacktestTask,
    val metrics: Metrics,
    val trades: List<TradeRecord>
)

data class PeriodResult(
    val periodName: String,
    val result: BacktestResult
)

data class CandidateEvaluation(
    val params: StrategyParams,
    val score: Double,
    val periodResults: List<PeriodResult>,
    val stabilityScore: Double,
    val passedHardFilters: Boolean,
    val rejectReason: String? = null
)

data class WalkForwardWindow(
    val trainStart: LocalDateTime,
    val trainEnd: LocalDateTime,
    val testStart: LocalDateTime,
    val testEnd: LocalDateTime,
    val name: String
)

data class WalkForwardResult(
    val params: StrategyParams,
    val windows: List<PeriodResult>,
    val passed: Boolean,
    val summaryScore: Double
)

data class StrategySnapshot(
    val strategyId: String,
    val strategyName: String,
    val params: StrategyParams,
    val score: Double,
    val metricsSummary: Map<String, Double>,
    val version: String,
    val status: String,
    val createdAt: LocalDateTime
)

data class NamedPeriod(
    val name: String,
    val start: LocalDateTime,
    val end: LocalDateTime
)
