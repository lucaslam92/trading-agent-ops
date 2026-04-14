package evolution

import java.io.File
import java.time.LocalDateTime

class StrategyRegistry(
    private val baseDir: File
) {
    init {
        if (!baseDir.exists()) baseDir.mkdirs()
    }

    fun save(snapshot: StrategySnapshot) {
        val file = File(baseDir, "${snapshot.strategyId}.json")
        val json = """
        {
          \"strategyId\": \"${snapshot.strategyId}\",
          \"strategyName\": \"${snapshot.strategyName}\",
          \"score\": ${snapshot.score},
          \"version\": \"${snapshot.version}\",
          \"status\": \"${snapshot.status}\",
          \"createdAt\": \"${snapshot.createdAt}\",
          \"params\": {
            \"maWindow\": ${snapshot.params.maWindow},
            \"adxWindow\": ${snapshot.params.adxWindow},
            \"adxThreshold\": ${snapshot.params.adxThreshold},
            \"swingWindow\": ${snapshot.params.swingWindow},
            \"retestToleranceAtr\": ${snapshot.params.retestToleranceAtr},
            \"stopAtrMultiplier\": ${snapshot.params.stopAtrMultiplier},
            \"trailingAtrMultiplier\": ${snapshot.params.trailingAtrMultiplier},
            \"minHoldingBars\": ${snapshot.params.minHoldingBars}
          }
        }
        """.trimIndent()
        file.writeText(json)
    }
}

class StrategyEvolutionEngine(
    private val candidateGenerator: CandidateGenerator,
    private val backtestRunner: BacktestRunner,
    private val evaluator: StrategyEvaluator,
    private val selector: StrategySelector,
    private val walkForwardValidator: WalkForwardValidator,
    private val registry: StrategyRegistry
) {

    fun evolve(
        spec: StrategySpec,
        candidateCount: Int,
        symbol: String,
        timeframe: String,
        trainPeriods: List<NamedPeriod>,
        walkForwardWindows: List<WalkForwardWindow>,
        topN: Int = 20
    ): List<WalkForwardResult> {

        val paramsList = candidateGenerator.generate(spec, candidateCount)
        println("[evolution] generated candidates: ${paramsList.size}")

        val evaluations = paramsList.mapIndexed { index, params ->
            println("[evolution] evaluating candidate ${index + 1}/${paramsList.size}: $params")
            val periodResults = trainPeriods.map { period ->
                val task = BacktestTask(
                    strategyName = spec.strategyName,
                    params = params,
                    symbol = symbol,
                    timeframe = timeframe,
                    start = period.start,
                    end = period.end
                )
                PeriodResult(
                    periodName = period.name,
                    result = backtestRunner.run(task)
                )
            }
            evaluator.evaluate(params, periodResults)
        }

        val rejected = evaluations.filter { !it.passedHardFilters }
        val rejectStats = rejected.groupingBy { it.rejectReason ?: "unknown" }.eachCount()
        val allMetrics = evaluations.map { mergeMetricsForDebug(it) }
        printMetricDistribution("profitFactor", allMetrics.map { it.profitFactor })
        printMetricDistribution("sharpe", allMetrics.map { it.sharpe })
        printMetricDistribution("netPnl", allMetrics.map { it.netPnl })
        printPfBuckets(allMetrics.map { it.profitFactor })
        printTopCandidates(allMetrics)
        printParamPfRelationships(allMetrics)

        println("[evolution] passed hard filters: ${evaluations.count { it.passedHardFilters }} / ${evaluations.size}")
        if (rejectStats.isNotEmpty()) {
            println("[evolution] reject reasons: $rejectStats")
        }

        val topCandidates = selector.selectTop(evaluations, topN)
        println("[evolution] selected top candidates: ${topCandidates.size}")

        val validated = topCandidates.mapIndexed { index, candidate ->
            println("[evolution] validating top candidate ${index + 1}/${topCandidates.size}: score=${candidate.score}")
            walkForwardValidator.validate(
                strategyName = spec.strategyName,
                params = candidate.params,
                symbol = symbol,
                timeframe = timeframe,
                windows = walkForwardWindows
            )
        }.filter { it.passed }
            .sortedByDescending { it.summaryScore }

        println("[evolution] walk-forward passed: ${validated.size} / ${topCandidates.size}")

        validated.forEachIndexed { index, result ->
            registry.save(
                StrategySnapshot(
                    strategyId = "${spec.strategyName}_${System.currentTimeMillis()}_$index",
                    strategyName = spec.strategyName,
                    params = result.params,
                    score = result.summaryScore,
                    metricsSummary = mapOf(
                        "walk_forward_score" to result.summaryScore,
                        "window_count" to result.windows.size.toDouble()
                    ),
                    version = "v1",
                    status = "stable_candidate",
                    createdAt = LocalDateTime.now()
                )
            )
        }

        return validated
    }

    private data class CandidateMetricsView(
        val params: StrategyParams,
        val score: Double,
        val profitFactor: Double,
        val sharpe: Double,
        val netPnl: Double,
        val grossPnl: Double,
        val feeRatio: Double,
        val avgHoldingHours: Long,
        val totalTrades: Int
    )

    private fun mergeMetricsForDebug(evaluation: CandidateEvaluation): CandidateMetricsView {
        val metrics = evaluation.periodResults.map { it.result.metrics }
        val totalTrades = metrics.sumOf { it.totalTrades }
        val grossPnl = metrics.sumOf { it.grossPnl }
        val netPnl = metrics.sumOf { it.netPnl }
        val totalFee = metrics.sumOf { it.totalFee }
        val profitFactor = metrics.map { it.profitFactor }.average()
        val sharpe = metrics.map { it.sharpe }.average()
        val avgHoldingHours = metrics.map { it.avgHoldingTime.toHours() }.average().toLong()
        val feeRatio = if (grossPnl <= 0.0) Double.POSITIVE_INFINITY else totalFee / grossPnl
        return CandidateMetricsView(
            params = evaluation.params,
            score = evaluation.score,
            profitFactor = profitFactor,
            sharpe = sharpe,
            netPnl = netPnl,
            grossPnl = grossPnl,
            feeRatio = feeRatio,
            avgHoldingHours = avgHoldingHours,
            totalTrades = totalTrades
        )
    }

    private fun printMetricDistribution(name: String, values: List<Double>) {
        if (values.isEmpty()) return
        val sorted = values.sorted()
        fun pct(p: Double): Double = sorted[((sorted.size - 1) * p).toInt()]
        println("[evolution] $name distribution: min=${sorted.first()} p25=${pct(0.25)} p50=${pct(0.50)} p75=${pct(0.75)} max=${sorted.last()}")
    }

    private fun printPfBuckets(values: List<Double>) {
        val buckets = linkedMapOf(
            "pf_lt_1_0" to values.count { it < 1.0 },
            "pf_1_0_to_1_1" to values.count { it >= 1.0 && it < 1.1 },
            "pf_1_1_to_1_2" to values.count { it >= 1.1 && it < 1.2 },
            "pf_1_2_to_1_25" to values.count { it >= 1.2 && it < 1.25 },
            "pf_ge_1_25" to values.count { it >= 1.25 }
        )
        println("[evolution] pf buckets: $buckets")
    }

    private fun printTopCandidates(allMetrics: List<CandidateMetricsView>) {
        val top = allMetrics.sortedByDescending { it.profitFactor }.take(10)
        println("[evolution] top 10 candidates by profitFactor:")
        top.forEachIndexed { index, item ->
            println("[evolution] top ${index + 1}: params=${item.params} profitFactor=${item.profitFactor} sharpe=${item.sharpe} netPnl=${item.netPnl} grossPnl=${item.grossPnl} feeRatio=${item.feeRatio} avgHoldingHours=${item.avgHoldingHours} totalTrades=${item.totalTrades}")
        }
    }

    private fun printParamPfRelationships(allMetrics: List<CandidateMetricsView>) {
        fun <T> groupAvg(label: String, selector: (StrategyParams) -> T) {
            val grouped = allMetrics.groupBy { selector(it.params) }
                .mapValues { (_, items) -> items.map { it.profitFactor }.average() }
                .toSortedMap(compareBy { it.toString() })
            println("[evolution] pf by $label: $grouped")
        }

        groupAvg("stopAtrMultiplier", { it.stopAtrMultiplier })
        groupAvg("trailingAtrMultiplier", { it.trailingAtrMultiplier })
        groupAvg("retestToleranceAtr", { it.retestToleranceAtr })
        groupAvg("adxThreshold", { it.adxThreshold })
        groupAvg("minHoldingBars", { it.minHoldingBars })
    }
}
