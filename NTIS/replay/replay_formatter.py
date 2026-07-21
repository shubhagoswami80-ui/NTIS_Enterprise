"""
NTIS Replay Formatter
"""
class ReplayFormatter:
    @staticmethod
    def header(title):
        return f"{'='*60}\n{title}\n{'='*60}"

    @staticmethod
    def line(label, value):
        return f"{label:<25}: {value}"
