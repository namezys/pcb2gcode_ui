import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pcb2gcode_ui.options import OPTION_SPECS, bool_value, default_output_directory

LOGGER = logging.getLogger(__name__)
PCB2GCODE_BINARY = "pcb2gcode"


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    return_code: int
    output: str

    @property
    def ok(self) -> bool:
        return self.return_code == 0


def discover_binary() -> str:
    path = shutil.which(PCB2GCODE_BINARY)
    if not path:
        raise FileNotFoundError("pcb2gcode was not found on PATH")
    return path


def pcb2gcode_version(binary: str = "") -> CommandResult:
    executable = binary or discover_binary()
    return run_command([executable, "--version"], Path.cwd())


def build_arguments(values: dict[str, str], include_output_dir: bool = True) -> list[str]:
    args = ["--noconfigfile"]
    for spec in OPTION_SPECS:
        value = values.get(spec.key, "").strip()
        if not value:
            continue
        if spec.key == "output-dir" and not include_output_dir:
            continue
        if spec.kind == "bool":
            value = "true" if bool_value(value) else "false"
        args.append(f"--{spec.key}={value}")
    return args


def validate_with_binary(values: dict[str, str], binary: str = "") -> CommandResult:
    executable = binary or discover_binary()
    args = [executable, *build_arguments(values, include_output_dir=False), "--no-export=true"]
    with tempfile.TemporaryDirectory(prefix="pcb2gcode-ui-validate-") as temp_dir:
        LOGGER.debug("Validating pcb2gcode parameters in %r", temp_dir)
        return run_command(args, Path(temp_dir))


def generate_nc_files(values: dict[str, str], binary: str = "") -> CommandResult:
    executable = binary or discover_binary()
    output_dir = Path(values.get("output-dir", "").strip() or default_output_directory(values))
    output_dir.mkdir(parents=True, exist_ok=True)
    command_values = dict(values)
    command_values["output-dir"] = str(output_dir)
    args = [executable, *build_arguments(command_values)]
    LOGGER.debug("Generating NC files into %r", output_dir)
    return run_command(args, output_dir)


def run_command(command: list[str], cwd: Path) -> CommandResult:
    LOGGER.debug("Running command %r in %r", command, cwd)
    process = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return CommandResult(command=command, return_code=process.returncode, output=process.stdout)
