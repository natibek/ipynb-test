from typing import Any
from jupyter_client import KernelManager, BlockingKernelClient, kernelspec
import uuid
from contextlib import contextmanager
import json
import os
from threading import Lock
from pathlib import Path
import importlib.util
import sys

KERNEL_NAME = "ipynb_test_kernel_"
DISPLAY_NAME = "ipynb_test_kernel"


class Kernel:
    """Class for a kernel for each notebook. Contains kernel manager and client used to
    execute code.
    """

    def __init__(self) -> None:
        self._validate_env()
        self.ksm = kernelspec.KernelSpecManager()

        self.kernel_spec: dict[str, Any] | None = None
        self.kernel_name: str | None = None

        self.venv_path = os.getenv("VIRTUAL_ENV")

        self.lock = Lock()
        self.in_venv = self.venv_path is not None
        self.initialize()

    def _validate_env(self) -> None:
        """Check if `ipynb_test` was ran in a Python environment with `ipykernel` installed.

        Raises:
            Exception: If `ipynb_test` is ran outside a Python environment.
            ModuleNotFoundError: If `ipykernel` is not inside the Python environment.
        """
        if os.getenv("VIRTUAL_ENV") is None:
            raise Exception("`ipynb_test` was not run in a Python environment.")

        if importlib.util.find_spec('ipykernel') is None:
            raise ModuleNotFoundError("`ipykernel` package not found.")


    def initialize(self) -> None:
        """Initializes the kernel's kernel manager and kernel client.
        If kernel specs made by `ipykernel_test` are found, they are prioritized.
        """

        kernel_spec, kernel_name = self._get_target_kernel_spec()

        if not kernel_spec:
            kernel_spec, kernel_name = self._create_new_kernel_spec()

        self.kernel_spec = kernel_spec
        self.kernel_name = kernel_name

    def connect_to_kernel_by_name(self, kernel_name: str) -> None:
        """Connect with a kernel with the given name and start a `BlockingKernelClient`
        to use for code executation.

        Args:
            kernel_name: name of the kernel to connect to.
        """
        kernel_spec = self._get_target_kernel_spec(kernel_name=kernel_name)

        if kernel_spec:
            self.connect_to_kernel(kernel_spec, kernel_name)

    def _create_new_kernel_spec(self) -> tuple[dict[str, Any], str]:
        """Creates new kernel spec in the current python environment.

        Returns the kernel spec and kernel name.
        """
        kernel_name = KERNEL_NAME + self._generate_id()
        kernel_spec = self._install_custom_kernel(
            kernel_name=kernel_name,
            display_name=DISPLAY_NAME,
        )
        return kernel_spec, kernel_name

    def _generate_id(self) -> str:
        """Generate unique id to use in kernel names created by Erys to avoid collision.

        Returns a uuid hex.
        """
        return uuid.uuid4().hex[:5]

    def _install_custom_kernel(
        self, kernel_name: str, display_name: str
    ) -> dict[str, Any]:
        """Writes the kernel specs for a custom `erys` kernel to the virtual enrivonments
        jupyter path.

        Returns the created kernel spec.
        """
        spec_path: Path = self.kernel_path.joinpath(f"kernels/{kernel_name}")
        argv = [
            str(Path(self.venv_path).joinpath("bin/python")),
            "-Xfrozen_modules=off",
            "-m",
            "ipykernel_launcher",
            "-f",
            "{connection_file}",
        ]

        kernel_spec = {
            "argv": argv,
            "env": {},
            "display_name": display_name,
            "language": "python",
            "interrupt_mode": "signal",
            "metadata": {"debugger": True},
        }

        spec_path.mkdir(parents=True, exist_ok=True)
        with open(spec_path.joinpath("kernel.json"), "w") as spec_file:
            json.dump(kernel_spec, spec_file)

        return kernel_spec

    def _get_target_kernel_spec(
        self, kernel_name: str | None = None
    ) -> tuple[dict[str, Any], str]:
        """Goes through all the kernel specs and finds the for the kernel in the current python
        environment and check if it has the provided kernel name if any is.

        Returns: the kernel spec and kernel name.
        """
        kernel_specs: dict[str, Any] = self.ksm.get_all_specs()

        if not kernel_specs:
            return {}, ""

        target_kernel_spec = {}
        target_kernel_name = ""
        for name, spec in kernel_specs.items():
            resource_dir = spec["resource_dir"]
            if Path(resource_dir).is_relative_to(self.venv_path):
                target_kernel_spec = spec["spec"]
                target_kernel_name = name

                if kernel_name and name == kernel_name:
                    break
                elif kernel_name is None and name.startswith(KERNEL_NAME):
                    break

        return target_kernel_spec, target_kernel_name

    def connect_to_kernel(self, kernel_spec: dict[str, Any], kernel_name) -> KernelManager:
        """Connect with a kernel defined by the given kernel spec nad kernel name.
        Then start a `BlockingKernelClient` to use for code execution.

        Args:
            kernel_spec: spec for the kernel to connect to.
            kernel_name: name of the kernel
        """
        # self.shutdown_kernel()  # will shutdown existing client channels and kernel manager

        # kernel manager
        kernel_manager: KernelManager = KernelManager(kernel_name=kernel_name)  

        # need to manually provide kernel command so that it is not over ridden by
        # implementation
        kernel_manager.kernel_cmd = kernel_spec["argv"]
        kernel_manager.kernel_spec.argv = kernel_spec["argv"]
        kernel_manager.kernel_spec.language = kernel_spec["language"]
        kernel_manager.kernel_spec.display_name = kernel_spec["display_name"]
        kernel_manager.kernel_spec.env = kernel_spec["env"]
        kernel_manager.kernel_spec.interrupt_mode = kernel_spec["interrupt_mode"]
        kernel_manager.kernel_spec.metadata = kernel_spec["metadata"]

        return kernel_manager

    @contextmanager
    def client_factory(self):
        kernel_manager = self.connect_to_kernel(self.kernel_spec, self.kernel_name)
        kernel_manager.start_kernel()

        kernel_client: BlockingKernelClient = kernel_manager.client()  # kernel client
        kernel_client.start_channels()

        def executor(code: str):
            return self._run_code(kernel_client, code)

        try:
            yield executor
        finally:
            kernel_client.stop_channels()
            kernel_manager.shutdown_kernel(now=True)


    def _run_code(self, client: BlockingKernelClient, code: str) -> tuple[list[dict[str, Any]], bool]:
        """Run provided code string with the kernel. Uses the iopub channel to get results.

        Args:
            code: code string.

        Returns: the outputs of executing the code with the kernel, and whether an error was raised.
        """
        client.execute(code)

        # Read the output from the iopub channel
        outputs = []
        errored = False
        while True:
            try:
                msg = client.get_iopub_msg()
                msg_type = msg["header"]["msg_type"]
                match msg_type:
                    case "status":
                        if msg["content"]["execution_state"] == "idle":
                            break
                    case "stream" if msg["content"]["name"] == "stderr":
                        continue
                    case "display_data" | "stream" | "error" | "execute_result":
                        if msg_type == "error":
                            errored = True
                        output = msg["content"]
                        output["output_type"] = msg_type
                        outputs.append(output)

            except Exception:
                pass

        return outputs, errored

