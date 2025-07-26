import json
from pathlib import Path
from .cell import CodeCell, MarkdownCell
import os.path

class Notebook:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.rel_path = os.path.relpath(path, Path.cwd())
        self.invalid_json = False
        self.cells: list[CodeCell | MarkdownCell] = []

    def load_notebook(self) -> None:
        """Load notebook from a file. Iterate through the cells and generate the `CodeCell` and
        `MarkdownCell` objects from the serialized formats.
        """
        with open(self.path, "r") as notebook_file:
            # if the file is empty, trying to decode json will fail so early exit.
            self._invalid_json = False
            if self.path.stat().st_size == 0:
                return

            try:
                # if the json decoding fails then the notebook is bad
                content = json.load(notebook_file)
            except json.JSONDecodeError:
                self._invalid_json = True
                return

        for cell in content["cells"]:
            if cell["cell_type"] == "code":
                cell = CodeCell.from_nb(cell, self)
            elif cell["cell_type"] == "markdown":
                cell = MarkdownCell.from_nb(cell, self)

            self.cells.append(cell)

    def test(self, executor, seed, verbose: bool, match_output: bool) -> bool:
        """

        Returns whether the test passed.
        """
        seed_code = f"import random;random.seed({seed})"
        executor(seed_code)
        print(f"{self.rel_path}", end=" ")
        for cell in self.cells:

            passed = cell.test(executor, verbose, match_output)
            if passed:
                print(".", end="")
            else:
                print("x", end="")
        print()
    
    def query_by_index(self, index: int) -> CodeCell | MarkdownCell:
        """Return cell by index.
        
        Returns: the cell at the index.
        """
        return self.cells[index]

