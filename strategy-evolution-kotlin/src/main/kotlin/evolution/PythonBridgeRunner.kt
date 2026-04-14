package evolution

import java.io.File
import java.nio.file.Files
import java.time.Duration
import java.time.LocalDateTime

class PythonBridgeBacktestEngine(
    private val workspaceDir: File,
    private val pythonBin: String = "python3"
) {
    fun run(
        strategyName: String,
        symbol: String,
        timeframe: String,
        start: LocalDateTime,
        end: LocalDateTime,
        params: StrategyParams
    ): BacktestResult {
        val task = BacktestTask(
            strategyName = strategyName,
            params = params,
            symbol = symbol,
            timeframe = timeframe,
            start = start,
            end = end
        )

        val tempConfig = Files.createTempFile(workspaceDir.toPath().resolve("configs"), "kbridge_", ".json").toFile()
        tempConfig.writeText(buildConfigJson(task))

        val command = listOf(
            pythonBin,
            "scripts/run_backtest_bridge.py",
            "--config-path",
            tempConfig.absolutePath
        )

        val proc = ProcessBuilder(command)
            .directory(workspaceDir)
            .redirectErrorStream(true)
            .start()

        println("[bridge] temp config: ${tempConfig.absolutePath}")
        val output = proc.inputStream.bufferedReader().readText()
        val exitCode = proc.waitFor()
        if (exitCode != 0) {
            throw IllegalStateException("Python bridge failed: exitCode=$exitCode output=$output tempConfig=${tempConfig.absolutePath}")
        }

        return parseBridgeResult(task, output)
    }

    private fun buildConfigJson(task: BacktestTask): String {
        return """
        {
          \"mode\": \"backtest\",
          \"symbol\": \"${task.symbol}\",
          \"exchange\": \"LOCAL\",
          \"interval\": \"${task.timeframe}\",
          \"start\": \"${task.start.toLocalDate()}\",
          \"end\": \"${task.end.toLocalDate()}\",
          \"rate\": 0.0005,
          \"slippage\": 5.0,
          \"size\": 0.01,
          \"pricetick\": 0.1,
          \"capital\": 100000,
          \"strategy\": \"${mapStrategyName(task.strategyName)}\",
          \"strategy_setting\": {
            \"ma_window\": ${task.params.maWindow},
            \"adx_window\": ${task.params.adxWindow},
            \"adx_threshold\": ${task.params.adxThreshold},
            \"swing_window\": ${task.params.swingWindow},
            \"retest_tolerance_atr\": ${task.params.retestToleranceAtr},
            \"stop_atr_multiplier\": ${task.params.stopAtrMultiplier},
            \"trailing_atr_multiplier\": ${task.params.trailingAtrMultiplier},
            \"min_holding_bars\": ${task.params.minHoldingBars}
          }
        }
        """.trimIndent()
    }

    private fun mapStrategyName(strategyName: String): String {
        return when (strategyName) {
            "bos_retest_long" -> "BtcBosRetestLongStrategy"
            else -> strategyName
        }
    }

    private fun parseBridgeResult(task: BacktestTask, output: String): BacktestResult {
        fun extract(field: String): String? {
            val regex = Regex("\\\"$field\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"")
            return regex.find(output)?.groupValues?.get(1)
        }

        fun extractNumber(field: String): Double {
            return extract(field)?.replace("%", "")?.toDoubleOrNull() ?: 0.0
        }

        val metrics = Metrics(
            totalReturn = extractNumber("total_return"),
            annualReturn = extractNumber("annual_return"),
            maxDrawdown = extractNumber("max_drawdown"),
            sharpe = extractNumber("sharpe"),
            calmar = extractNumber("calmar"),
            totalTrades = extract("total_trades")?.toIntOrNull() ?: 0,
            winRate = extractNumber("win_rate"),
            avgWin = extractNumber("avg_win"),
            avgLoss = extractNumber("avg_loss"),
            profitFactor = extractNumber("profit_factor"),
            grossPnl = extractNumber("gross_pnl"),
            netPnl = extractNumber("net_pnl"),
            totalFee = extractNumber("total_fee"),
            avgHoldingTime = parseDuration(extract("avg_holding_time") ?: "0h"),
            longPnl = extractNumber("long_pnl"),
            shortPnl = extractNumber("short_pnl")
        )

        return BacktestResult(
            task = task,
            metrics = metrics,
            trades = emptyList()
        )
    }

    private fun parseDuration(text: String): Duration {
        val normalized = text.trim()
        if (normalized.endsWith("h") && !normalized.contains("d")) {
            val hours = normalized.removeSuffix("h").trim().toLongOrNull() ?: 0L
            return Duration.ofHours(hours)
        }
        if (normalized.contains("d")) {
            val dayPart = Regex("(\\d+)d").find(normalized)?.groupValues?.get(1)?.toLongOrNull() ?: 0L
            val hourPart = Regex("(\\d+)h").find(normalized)?.groupValues?.get(1)?.toLongOrNull() ?: 0L
            return Duration.ofHours(dayPart * 24 + hourPart)
        }
        return Duration.ZERO
    }
}

class PythonBridgeBacktestRunner(
    private val engine: PythonBridgeBacktestEngine
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
