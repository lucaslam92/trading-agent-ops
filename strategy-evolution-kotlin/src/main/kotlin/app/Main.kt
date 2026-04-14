package app

import evolution.*
import java.io.File
import java.time.LocalDateTime

fun main() {
    val spec = StrategySpecs.bosRetestLongSpec()
    val backtestRunner = PythonBridgeBacktestRunner(
        PythonBridgeBacktestEngine(File("/root/.openclaw/workspace"))
    )
    val evaluator = StrategyEvaluator(
        EvaluationConfig(
            minProfitFactor = 1.25,
            minSharpe = 0.3,
            minTrades = 15,
            minAvgHoldingHours = 18,
            maxFeeRatio = 0.35,
            requirePositiveLongPnl = true
        )
    )

    val engine = StrategyEvolutionEngine(
        candidateGenerator = CandidateGenerator(),
        backtestRunner = backtestRunner,
        evaluator = evaluator,
        selector = StrategySelector(),
        walkForwardValidator = WalkForwardValidator(
            backtestRunner = backtestRunner,
            evaluator = evaluator
        ),
        registry = StrategyRegistry(File("strategy_registry"))
    )

    val trainPeriods = listOf(
        NamedPeriod(
            name = "2023",
            start = LocalDateTime.of(2023, 1, 1, 0, 0),
            end = LocalDateTime.of(2023, 12, 31, 23, 59)
        ),
        NamedPeriod(
            name = "2024",
            start = LocalDateTime.of(2024, 1, 1, 0, 0),
            end = LocalDateTime.of(2024, 12, 31, 23, 59)
        )
    )

    val walkForwardWindows = listOf(
        WalkForwardWindow(
            trainStart = LocalDateTime.of(2023, 1, 1, 0, 0),
            trainEnd = LocalDateTime.of(2023, 6, 30, 23, 59),
            testStart = LocalDateTime.of(2023, 7, 1, 0, 0),
            testEnd = LocalDateTime.of(2023, 9, 30, 23, 59),
            name = "wf_2023_q3"
        ),
        WalkForwardWindow(
            trainStart = LocalDateTime.of(2023, 4, 1, 0, 0),
            trainEnd = LocalDateTime.of(2023, 12, 31, 23, 59),
            testStart = LocalDateTime.of(2024, 1, 1, 0, 0),
            testEnd = LocalDateTime.of(2024, 3, 31, 23, 59),
            name = "wf_2024_q1"
        )
    )

    val results = engine.evolve(
        spec = spec,
        candidateCount = 100,
        symbol = "BTC-USDT-SWAP",
        timeframe = "1h",
        trainPeriods = trainPeriods,
        walkForwardWindows = walkForwardWindows,
        topN = 20
    )

    println("Validated strategy count: ${results.size}")
    results.take(5).forEachIndexed { index, r ->
        println(
            """
            Rank ${index + 1}
            Params: ${r.params}
            Score: ${"%.4f".format(r.summaryScore)}
            Windows: ${r.windows.map { it.periodName }}
            """.trimIndent()
        )
    }
}
