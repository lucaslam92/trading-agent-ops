# strategy-evolution-kotlin

Kotlin MVP skeleton for Strategy Evolution Engine.

## Status
- Project skeleton created
- Core models, generator, evaluator, selector, validator, registry, engine, and main entry added
- `ExistingBacktestEngine` is still a stub and must be wired to the real backtest system

## Structure
- `src/main/kotlin/evolution` core modules
- `src/main/kotlin/app/Main.kt` run entry
- `build.gradle.kts` Gradle build file
- `settings.gradle.kts` Gradle settings

## Run
```bash
cd strategy-evolution-kotlin
./gradlew run
```

If Gradle wrapper is not present, use your local Gradle installation:
```bash
gradle run
```

## Next step
Implement one of these adapters:
- `ExistingBacktestEngine.run(...)` if a native Kotlin backtest engine becomes available
- `PythonBridgeBacktestEngine.run(...)` to bridge into the existing Python backtest system

A Python bridge design note is included at `src/main/kotlin/evolution/PythonBridgeDesign.md`.
