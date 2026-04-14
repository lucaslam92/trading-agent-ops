package evolution

class StrategySelector {

    fun selectTop(
        evaluations: List<CandidateEvaluation>,
        limit: Int
    ): List<CandidateEvaluation> {
        return evaluations
            .asSequence()
            .filter { it.passedHardFilters }
            .sortedByDescending { it.score }
            .take(limit)
            .toList()
    }
}

class WalkForwardValidator(
    private val backtestRunner: BacktestRunner,
    private val evaluator: StrategyEvaluator
) {

    fun validate(
        strategyName: String,
        params: StrategyParams,
        symbol: String,
        timeframe: String,
        windows: List<WalkForwardWindow>
    ): WalkForwardResult {
        val periodResults = windows.map { window ->
            val task = BacktestTask(
                strategyName = strategyName,
                params = params,
                symbol = symbol,
                timeframe = timeframe,
                start = window.testStart,
                end = window.testEnd
            )
            PeriodResult(
                periodName = window.name,
                result = backtestRunner.run(task)
            )
        }

        val evaluation = evaluator.evaluate(params, periodResults)
        return WalkForwardResult(
            params = params,
            windows = periodResults,
            passed = evaluation.passedHardFilters,
            summaryScore = evaluation.score
        )
    }
}
