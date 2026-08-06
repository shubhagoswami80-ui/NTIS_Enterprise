from pathlib import Path
import json


class AIContextGenerator:

    def __init__(self, metadata_file, output_root):
        self.metadata_file = Path(metadata_file)
        self.output_root = Path(output_root)

        self.output_root.mkdir(parents=True, exist_ok=True)

        with self.metadata_file.open(
            "r",
            encoding="utf-8"
        ) as f:
            self.meta = json.load(f)

    def generate(self):

        self.project_summary()

        self.module_registry()

        self.dependency_graph()

        self.runtime_registry()

        self.intelligence_index()

    def _save(self, name, obj):

        with (self.output_root / name).open(
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                obj,
                f,
                indent=4,
                ensure_ascii=False
            )

    def project_summary(self):

        obj = {

            "code_root": self.meta["code_root"],

            "data_root": self.meta["data_root"],

            "module_count":
                len(self.meta["folder_architecture"]["code"]),

            "runtime_files":
                len(self.meta["folder_architecture"]["data"]),

            "intelligence_modules":
                len(self.meta["intelligence"])

        }

        self._save(
            "project_summary.json",
            obj
        )

    def module_registry(self):

        self._save(

            "module_registry.json",

            self.meta["folder_architecture"]["code"]

        )

    def dependency_graph(self):

        self._save(

            "dependency_graph.json",

            self.meta["dependencies"]

        )

    def runtime_registry(self):

        self._save(

            "runtime_registry.json",

            self.meta["folder_architecture"]["data"]

        )

    def intelligence_index(self):

        self._save(

            "intelligence_index.json",

            self.meta["intelligence"]

        )