# Repository Guidelines

## Project Structure & Module Organization
This is a new repository. `main.py` is the current Python entrypoint. `pyproject.toml`
defines the `pcb2gcode-ui` package and Python `>=3.14`. `pcb2gcode/` contains the
bundled C++ pcb2gcode project: source in `src/`, CMake config in `CMakeLists.txt`,
tests in `tests/`, fixtures in `tests/data/`, helper scripts in `tools/`, and examples
or assets in `extras/`. Keep generated build output under `pcb2gcode/build/`.

## Build, Test, and Development Commands
- `python -m venv .venv`: create the root virtual environment.
- `.venv/bin/python main.py`: run the current Python entrypoint.
- `cmake -S pcb2gcode -B pcb2gcode/build -DCMAKE_BUILD_TYPE=Release`: configure C++ build.
- `cmake --build pcb2gcode/build`: build the C++ executable and tests.
- `ctest --test-dir pcb2gcode/build --output-on-failure`: run registered CTest tests.
- `.venv/bin/python -m pytest <path>`: run Python tests when added.

## Coding Style & Naming Conventions
Python uses PEP 8, 4-space indentation, type hints, `ruff`, and `flake8` when configured.
Do not use `from __future__ import annotations`. If a default value is `None`, do not
include `None` in the annotation union. Use `typing.Self` for fluent methods. Use
`snake_case` for modules and functions, and `CamelCase` for classes. Avoid trailing
underscores, one-letter names in multi-line loops, and similar names in one scope.
Extract constants except for obvious `0`, `1`, and empty strings. Use
`logging.getLogger(__name__)`, lazy `%s` formatting, and no f-strings in logs. C++ changes
should match existing `pcb2gcode/src` style and preserve C++14 compatibility.

## Testing Guidelines
Use `pytest` for Python; name test files `test_*.py`. Prefer behavior assertions and
targeted test paths. Use CTest for C++; add Boost test files under `pcb2gcode/tests/`
and fixtures under `pcb2gcode/tests/data/`.

## Commit & Pull Request Guidelines
No local commit history exists yet. Use short imperative commits, such as
`Add UI entrypoint`. Pull requests should include purpose, changed areas, test results,
linked issues when available, and screenshots for UI-visible changes.

## Agent-Specific Instructions
Call the user Nik. Use direct file access for listing, reading, searching, and git state.
Use PyCharm MCP for IDE analysis or warnings. Make surgical edits, state assumptions when
ambiguous, and verify changed behavior.
