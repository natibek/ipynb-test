import json
from pathlib import Path
from .cell import CodeCell, MarkdownCell
import uuid
import os.path

class Notebook:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.rel_path = os.path.relpath(path, Path.cwd())
        self.invalid_json = False
        self.num_code_cells = 0
        self.cells: list[CodeCell | MarkdownCell] = []
        self.failed: list[CodeCell] = []

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
                self.num_code_cells += 1
            elif cell["cell_type"] == "markdown":
                cell = MarkdownCell.from_nb(cell, self)

            self.cells.append(cell)

    def _generate_id(self, length: 5) -> str:
        return uuid.uuid4().hex[:length]
    
    def test(self, executor, seed: int, seed_numpy: bool, match_output: bool, continue_after_fail: bool) -> bool:
        """

        Returns whether the test passed.
        """
        func_id = self._generate_id()
        seed_code = f"from random import seed as seed_{func_id};seed_{func_id}({seed});"
        if seed_numpy:
            numpy_seed_code = f"from numpy.random import seed as n_seed_{func_id}; n_seed_{func_id}({seed});"
            seed_code += numpy_seed_code

        executor(seed_code)
        print(f"{self.rel_path}", end=" ")
        for cell in enumerate(self.cells):

            passed = cell.test(executor, match_output)
            if passed:
                print(".", end="")
            else:
                self.failed.append(cell)
                print("x", end="")
                if not continue_after_fail: break
        print("\n")

    def report(self, verbose: bool) -> None:
        for cell in self.failed:
            cell.report(verbose)
            print()

    def query_by_index(self, index: int) -> CodeCell | MarkdownCell:
        """Return cell by index.
        
        Returns: the cell at the index.
        """
        return self.cells[index]

