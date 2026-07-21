"""
NTIS Replay Visualizer
"""
class ReplayVisualizer:
    def summary(self, stats: dict):
        for k, v in stats.items():
            print(f"{k}: {v}")
