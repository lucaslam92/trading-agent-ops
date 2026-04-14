package evolution

import java.util.Random

class CandidateGenerator(
    private val random: Random = Random()
) {
    fun generate(spec: StrategySpec, count: Int): List<StrategyParams> {
        val set = linkedSetOf<StrategyParams>()
        while (set.size < count) {
            set += spec.randomParamFactory(random)
        }
        return set.toList()
    }
}

object StrategySpecs {

    fun bosRetestLongSpec(): StrategySpec {
        return StrategySpec("bos_retest_long") { random ->
            StrategyParams(
                maWindow = random.nextInt(30, 81),
                adxWindow = random.nextInt(10, 21),
                adxThreshold = random.nextDouble(18.0, 24.1),
                swingWindow = random.nextInt(20, 41),
                retestToleranceAtr = random.nextDouble(0.3, 0.71),
                stopAtrMultiplier = random.nextDouble(1.2, 1.9),
                trailingAtrMultiplier = random.nextDouble(2.0, 3.1),
                minHoldingBars = random.nextInt(24, 49)
            )
        }
    }
}
