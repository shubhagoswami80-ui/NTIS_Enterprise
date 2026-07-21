"""
NTIS Replay Report Formatter
"""
class ReplayReportFormatter:
    @staticmethod
    def format(title, lines):
        output = ["=" * 60, title, "=" * 60]
        output.extend(str(line) for line in lines)
        return "\n".join(output)
