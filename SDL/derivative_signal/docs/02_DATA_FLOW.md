# Data Flow

```text
Existing Daywise source
        |
        v
Existing SDL source discovery
        |
        | read/reuse
        v
derivative_signal
        |
        +--> current OHLC
        +--> previous snapshot
        +--> primary OI evidence
        +--> PE/CE OI evidence
        |
        v
Decision Signal Engine
        |
        +--> WATCH
        +--> DEVELOPING
        +--> NO_TRADE
        +--> INSUFFICIENT_DATA
        |
        v
Decision Dashboard
```

The layer does not duplicate the upstream data pipeline and does not modify source files.
