# W73 architecture

Existing live pipeline (READ ONLY)
        |
        v
03_LIVE_ADAPTER
        |
        v
point-in-time W73 snapshot
        |
        +----> 02_FEATURE_ENGINE
        |             |
        |             v
        |        W73 Strategy
        |             |
        |        +----+----+
        |        |         |
        |        v         v
        |    Decision   06_ALERTS
        |      Board
        |
        +----> 04_REPLAY

Historical evidence and research required by W73 are inside this folder.

No W73 runtime module imports old SDL research/application modules.
