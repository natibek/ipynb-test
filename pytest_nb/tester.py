from .notebook import Notebook
from .kernel import Kernel
from . import __version__
from argparse import ArgumentParser
from pathlib import Path
from threading import Thread
import time
import importlib.util

class Tester:
    def __init__(self) -> None:
        self.kernel = Kernel()
        self.num_threads = 1
        self.notebooks: list[Notebook] = []
        self.seed = int(time.time())
        self.seed_numpy = importlib.util.find_spec("numpy") is not None

    def cli(self) -> None:
        parser = ArgumentParser(
            "ipynb-test",
            description="Seedable Jupyter Notebook testing tool.",
        )

        parser.add_argument(
            "notebooks", nargs="*", help="Jupyter notebooks to test.", type=Path
        )
        parser.add_argument("--version", action="version", version=__version__)
        parser.add_argument("-j", "--num-threads", type=int, default=self.num_threads, help="Number of threads to use for testing.")
        parser.add_argument("-s", "--seed", type=int, default=self.seed, help="Seed to use for testing.")
        parser.add_argument("-m", "--match-output", action="store_true", help="Check if test cell output matches cell outputs.")
        parser.add_argument("-c", "--continue-on-fail", action="store_true", help="Continue testing notebook after a cell fails.")
        parser.add_argument("-v", "--verbose", action="store_true", help="Verbose reporting.")
        args = parser.parse_args()

        self.num_threads = args.num_threads
        self.seed = args.seed
        self.verbose = args.verbose
        self.match_output = args.match_output
        self.continue_on_fail = args.continue_on_fail

        for notebook in args.notebooks:
            nb = Notebook(notebook)
            nb.load_notebook()
            self.notebooks.append(nb)


    def test_notebook(self, notebook: Notebook) -> None:
        with self.kernel.client_factory() as executor:
            notebook.test(executor, self.seed, self.seed_numpy, self.match_output, self.continue_on_fail)

    def test(self) -> None:
        print(f"Testing with seed {self.seed}\n")
        for notebook in self.notebooks:
            self.test_notebook(notebook)

    def report(self) -> None:
        print("Reporting\n")
        for notebook in self.notebooks:
            notebook.report(self.verbose)

def run_tester() -> None:
    tester = Tester()
    tester.cli()
    tester.test()
    tester.report()

if __name__ == "__main__":
    run_tester()