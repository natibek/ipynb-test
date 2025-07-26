from typing import Any

class CodeCell:
    cell_type = "code"
    def __init__(
        self,
        source: str,
        outputs: list[str],
        exec_count: int | None,
        metadata: dict[str, Any],
        cell_id: int | None,
    ) -> None:
        self.source = source
        self.original_outputs = outputs
        self.exec_count = exec_count
        self.metadata = metadata
        self.cell_id = cell_id

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

    def test(self, executor, verbose: bool, match_output: bool) -> bool:
        """

        Return whether the test passed. 
        """
        exec_outputs, errored = executor(self.source)
        if errored:
            if verbose: self.report_error(exec_outputs[-1])
            return False

        elif match_output:
            return self.test_match(exec_outputs)
        
        return True

    def test_match(self, exec_outputs: list[dict[str, Any]]) -> bool:
        """

        Returns whether the execution outputs match the outputs in a notebook.
        """
        if len(exec_outputs) != len(self.original_outputs): return False

        for exec_output, original_output in zip(exec_outputs, self.original_outputs):
            if exec_output["output_type"] != original_output["output_type"]:
                return False

            match exec_output["output_type"]:
                case "stream":
                    if not self._test_match_stream(exec_output, original_output):
                        return False
                case "error":
                    if not self._test_match_error(exec_output, original_output):
                        return False
                case "display_data" | "execute_result": 
                    if not self._test_match_execute_result(exec_output, original_output):
                        return False

        return True
    
    def _compare_multiline_text(self, exec_text, original_text) -> bool:
        exec_text = "".join(exec_text) if isinstance(exec_text, list) else exec_text
        original_text = "".join(original_text) if isinstance(original_text, list) else original_text
        return exec_text == original_text

    def _test_match_stream(self, exec_output, original_output) -> bool:
        # {
        #   "output_type" : "stream",
        #   "name" : "stdout", # or stderr
        #   "text" : ["multiline stream text"],
        # }
        if exec_output["name"] != original_output["name"]:
            return False

        return self._compare_multiline_text(exec_output["text"], original_output["text"])

    def _test_match_error(self, exec_output, original_output) -> bool:
        # {
        #   "output_type" : "error",
        #   'ename' : str,   # Exception name, as a string
        #   'evalue' : str,  # Exception value, as a string
        #   'traceback' : list,
        # }
        return all(exec_output[key] == original_output[key] for key in ["ename", "evalue", "traceback"])

    def _test_match_execute_result(self, exec_output, original_output) -> bool:
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
        # }    def _test_match_display_data(self, exec_output, original_output) -> bool:
        exec_data = exec_output["data"]
        exec_metadata = exec_output["metadata"]
        original_data = original_output["data"]
        original_metadata = original_output["metadata"]
        if exec_data.keys() != original_data.keys():
            return False

        for key in exec_data.keys():
            match key:
                case "text/plain":
                    if not self._compare_multiline_text(exec_data[key], original_data[key]):
                        return False
                case "application/json":
                    if exec_data[key] != original_data[key]:
                        return False
                case "image/png":
                    if exec_data[key] != original_data[key]:
                        return False
                    if exec_metadata.get(key) != original_metadata.get(key):
                        return False

        return True



    def report_error(self, error_msg: dict[str, Any]) -> None:
        # {
        #   "output_type" : "error",
        #   'ename' : str,   # Exception name, as a string
        #   'evalue' : str,  # Exception value, as a string
        #   'traceback' : list,
        # }
        traceback = error_msg["traceback"]

        if isinstance(traceback, list):
            traceback = "\n".join(traceback)

        print(traceback)

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

    def test(self, executor, verbose: bool, match_output: bool) -> bool:
        return True