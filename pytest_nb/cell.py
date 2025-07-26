from typing import Any

class CodeCell:
    cell_type = "code"
    def __init__(
        self,
        source: str,
        outputs: list[dict[str, Any]],
        exec_count: int | None,
        metadata: dict[str, Any],
        cell_id: int | None,
    ) -> None:
        self.source = source
        self.original_outputs = outputs
        self.exec_count = exec_count
        self.metadata = metadata
        self.cell_id = cell_id

        self.test_outputs = []
        self.expected = None
        self.found = None
        self.error = None

    @staticmethod
    def from_nb(nb: dict[str, Any], notebook) -> "CodeCell":
        """Static method to generate a `CodeCell` from a json/dict that represent a code cell.

        Args:
            nb: the notebook json/dict format of the code cell.
            notebook: the `Notebook` object the code cell belongs too.

        Returns: `CodeCell` from notebook format.

        Raises:
            AssertionError: if no notebook or bad notebook representation.
        """
        # need to have a notebook object and a notebook format
        assert nb
        assert notebook
        # needs to be a valid notebook representation
        for key in ["cell_type", "execution_count", "metadata", "source", "outputs"]:
            assert key in nb
        assert nb["cell_type"] == "code"

        source = nb["source"]
        if isinstance(source, list):
            # join the strings if the input was a multiline string
            source = "".join(source)

        return CodeCell(
            source=source,
            outputs=nb["outputs"],
            exec_count=nb["execution_count"],
            metadata=nb["metadata"],
            cell_id=nb.get("id", None),
        )

    def test(self, executor, match_output: bool) -> bool:
        """

        Return whether the test passed. 
        """
        test_outputs, errored = executor(self.source)
        self.test_outputs = test_outputs

        if errored:
            self.error = test_outputs[-1]
            return False

        elif match_output:
            return self.test_match(test_outputs)
            
        
        return True

    def test_match(self, test_outputs: list[dict[str, Any]]) -> bool:
        """

        Returns whether the execution outputs match the outputs in a notebook.
        """
        if len(test_outputs) != len(self.original_outputs):
            self.expected = f"{len(self.original_outputs)} outputs"
            self.found = f"{len(test_outputs)} outputs"
            return False

        for test_output, original_output in zip(test_outputs, self.original_outputs):
            if test_output["output_type"] != original_output["output_type"]:
                self.expected = original_output
                self.found = test_output
                return False

            match test_output["output_type"]:
                case "stream":
                    if not self._test_match_stream(test_output, original_output):
                        self.expected = original_output
                        self.found = test_output
                        return False
                case "error":
                    if not self._test_match_error(test_output, original_output):
                        return False
                case "display_data" | "execute_result": 
                    if not self._test_match_execute_result(test_output, original_output):
                        return False

        return True

    def _handle_multiline_test(self, multiline_text: list[str] | str) -> str:
        return "".join(multiline_text) if isinstance(multiline_text, list) else multiline_text

    def _test_match_stream(self, test_output, original_output) -> bool:
        # {
        #   "output_type" : "stream",
        #   "name" : "stdout", # or stderr
        #   "text" : ["multiline stream text"],
        # }
        if test_output["name"] != original_output["name"]:
            self.expected = original_output
            self.found = test_output
            return False

        test_text = self._handle_multiline_test(test_output["text"])
        original_text = self._handle_multiline_test(original_output["text"])
        if test_text != original_text:
            self.expected = original_output
            self.found = test_output
            return False

        return True

    def _test_match_error(self, test_output, original_output) -> bool:
        # {
        #   "output_type" : "error",
        #   'ename' : str,   # Exception name, as a string
        #   'evalue' : str,  # Exception value, as a string
        #   'traceback' : list,
        # }
        return all(test_output[key] == original_output[key] for key in ["ename", "evalue", "traceback"])

    def _test_match_execute_result(self, test_output, original_output) -> bool:
        # the display_data and output_result have different formats
        # {
        #   "output_type" : "execute_result" | "display_data",
        #   "execution_count": 42, # if "execute_result"
        #   "data" : {
        #     "text/plain" : ["multiline text data"],
        #     "image/png": ["base64-encoded-png-data"],
        #     "application/json": {
        #       # JSON data is included as-is
        #       "json": "data",
        #     },
        #   },
        #   "metadata" : {
        #     "image/png": {
        #       "width": 640,
        #       "height": 480,
        #     },
        #   },
        # }    def _test_match_display_data(self, test_output, original_output) -> bool:
        test_data = test_output["data"]
        test_metadata = test_output["metadata"]
        original_data = original_output["data"]
        original_metadata = original_output["metadata"]

        if test_data.keys() != original_data.keys():
            self.expected = original_data.keys()
            self.found = test_data.keys()
            return False

        for key in test_data.keys():
            match key:
                case "text/plain":
                    test_text = self._handle_multiline_test(test_data[key])
                    original_text = self._handle_multiline_test(original_data[key])
                    if test_text != original_text:
                        self.expected = original_text
                        self.found = test_text
                        return False

                case "application/json":
                    if test_data[key] != original_data[key]:
                        self.expected = original_data[key]
                        self.found = test_data[key]
                        return False

                case "image/png":
                    if test_data[key] != original_data[key]:
                        self.expected = original_data[key]
                        self.found = test_data[key]
                        return False
                    if test_metadata.get(key) != original_metadata.get(key):
                        self.expected = original_data[key]
                        self.found = test_data[key]
                        return False

        return True

    def _report_mismatch(self, expected, found) -> None:
        print("Expected")
        print(f"{expected}")
        print("Found")
        print(f"{found}")

    def _report_error(self) -> None:
        # {
        #   "output_type" : "error",
        #   'ename' : str,   # Exception name, as a string
        #   'evalue' : str,  # Exception value, as a string
        #   'traceback' : list,
        # }
        traceback = self.error["traceback"]

        if isinstance(traceback, list):
            traceback = "\n".join(traceback)

        print("Error")
        print(traceback)
    
    def report(self, verbose: bool) -> None:
        if verbose:
            print("Verbose")
            print("Original Output")
            print(self.original_outputs)

            print("Test Outputs")
            print(self.test_outputs)

        if self.error:
            self._report_error()
        elif self.found and self.expected:
            self._report_mismatch(self.expected, self.found)
        


class MarkdownCell:
    cell_type = "markdown"

    def __init__(
        self,
        source: str,
        metadata: dict[str, Any],
        cell_id: str | None,
    ) -> None:
        self.source = source
        self.metadata = metadata
        self.cell_id = cell_id

    @staticmethod
    def from_nb(nb: dict[str, Any]) -> "MarkdownCell":
        """
        """
        # need to have a notebook object and a notebook format
        assert nb
        # needs to be a valid notebook representation
        for key in ["cell_type", "metadata", "source"]:
            assert key in nb
        assert nb["cell_type"] == "markdown"

        source = nb["source"]
        if isinstance(source, list):
            # join the strings if the input was a multiline string
            source = "".join(source)

        return MarkdownCell(
            source=source,
            metadata=nb["metadata"],
            cell_id=nb.get("id"),
        )

    def test(self, executor, match_output: bool) -> bool:
        return True