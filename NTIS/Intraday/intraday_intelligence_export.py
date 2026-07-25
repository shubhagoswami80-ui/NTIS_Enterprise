from pathlib import Path

class IntelligenceExport:
    def export(self, df, file):
        df.to_csv(Path(file), index=False)
        return file
