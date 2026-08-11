"""
NTIS Intraday Junk Data Analyzer
"""

from pathlib import Path

class IntradayJunkDataAnalyzer:

    def analyze(self, folder):

        result = []

        for f in Path(folder).rglob("*"):
            if f.is_file() and f.name.startswith("~$"):
                result.append(str(f))

        return result
