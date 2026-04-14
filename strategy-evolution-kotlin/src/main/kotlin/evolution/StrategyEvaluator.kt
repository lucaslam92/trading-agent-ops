package evolution

import java.time.Duration
import kotlin.math.abs
import kotlin.math.sqrt

data class EvaluationConfig(
    val minProfitFactor: Double = 1.25,
    val minSharpe: Double = 0.3,
    val minTrades: Int = 15,
    val minAvgHoldingHours: Long = 18,
    val maxFeeRatio: Double = 0.35,
    val requirePositiveLongPnl: Boolean = true
)

class StrategyEvaluator(
    private val config: EvaluationConfig = EvaluationConfig()
) {

    fun evaluate(params: StrategyParams, periodResults: List<PeriodResult>): CandidateEvaluation {
        val merged = mergeMetrics(periodResults.map { it.result.metrics })

        val rejectReason = checkHardFilters(merged)
        if (rejectReason != null) {
            return CandidateEvaluation(
                params = params,
                score = Double.NEGATIVE_INFINITY,
                periodResults = periodResults,
                stabilityScore = 0.0,
                passedHardFilters = false,
                rejectReason = rejectReason
            )
        }

        val stabilityScore = computeStabilityScore(periodResults.map { it.result.metrics.annualReturn })
        val score = computeScore(merged, stabilityScore)

        return CandidateEvaluation(
            params = params,
            score = score,
            periodResults = periodResults,
            stabilityScore = stabilityScore,
            passedHardFilters = true
        )
    }

    private fun checkHardFilters(m: Metrics): String? {
        if (m.profitFactor < config.minProfitFactor) return "profit_factor_too_low"
        if (m.sharpe < config.minSharpe) return "sharpe_too_low"
        if (m.totalTrades < config.minTrades) return "total_trades_too_low"
        if (m.avgHoldingTime.toHours() < config.minAvgHoldingHours) return "avg_holding_time_too_low"
        if (m.feeRatio > config.maxFeeRatio) return "fee_ratio_too_high"
        if (config.requirePositiveLongPnl && m.longPnl <= 0.0) return "long_pnl_not_positive"
        return null
    }

    private fun computeScore(m: Metrics, stabilityScore: Double): Double {
        val pf = normalize(m.profitFactor, 1.0, 2.5)
        val sharpe = normalize(m.sharpe, 0.0, 2.0)
        val calmar = normalize(m.calmar, 0.0, 2.0)
        val netPnl = normalize(m.netPnl, 0.0, 100.0)
        val feePenalty = 1.0 - normalize(m.feeRatio, 0.0, 0.5)

        return (
            0.30 * pf +
                0.25 * sharpe +
                0.15 * calmar +
                0.15 * netPnl +
                0.10 * stabilityScore +
                0.05 * feePenalty
            )
    }

    private fun computeStabilityScore(annualReturns: List<Double>): Double {
        if (annualReturns.isEmpty()) return 0.0
        if (annualReturns.size == 1) return 1.0

        val mean = annualReturns.average()
        val variance = annualReturns.map { (it - mean) * (it - mean) }.average()
        val std = sqrt(variance)

        return 1.0 / (1.0 + abs(std))
    }

    private fun normalize(value: Double, min: Double, max: Double): Double {
        if (value.isNaN()) return 0.0
        if (max <= min) return 0.0
        return ((value - min) / (max - min)).coerceIn(0.0, 1.0)
    }

    private fun mergeMetrics(metricsList: List<Metrics>): Metrics {
        require(metricsList.isNotEmpty())

        val totalTrades = metricsList.sumOf { it.totalTrades }
        val grossPnl = metricsList.sumOf { it.grossPnl }
        val netPnl = metricsList.sumOf { it.netPnl }
        val totalFee = metricsList.sumOf { it.totalFee }

        return Metrics(
            totalReturn = metricsList.map { it.totalReturn }.average(),
            annualReturn = metricsList.map { it.annualReturn }.average(),
            maxDrawdown = metricsList.maxOf { it.maxDrawdown },
            sharpe = metricsList.map { it.sharpe }.average(),
            calmar = metricsList.map { it.calmar }.average(),
            totalTrades = totalTrades,
            winRate = metricsList.map { it.winRate }.average(),
            avgWin = metricsList.map { it.avgWin }.average(),
            avgLoss = metricsList.map { it.avgLoss }.average(),
            profitFactor = metricsList.map { it.profitFactor }.average(),
            grossPnl = grossPnl,
            netPnl = netPnl,
            totalFee = totalFee,
            avgHoldingTime = averageDuration(metricsList.map { it.avgHoldingTime }),
            longPnl = metricsList.sumOf { it.longPnl },
            shortPnl = metricsList.sumOf { it.shortPnl }
        )
    }

    private fun averageDuration(durations: List<Duration>): Duration {
        val avgMillis = durations.map { it.toMillis() }.average().toLong()
        return Duration.ofMillis(avgMillis)
    }
}
