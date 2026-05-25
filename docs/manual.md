# pcb2gcode-ui User Manual

This manual describes the normal operator workflow for `pcb2gcode-ui`: loading board files,
checking the preview, validating `pcb2gcode` parameters, and generating NC files.

The app is a graphical parameter editor and preview tool for `pcb2gcode`. The generated NC files
still come from the installed `pcb2gcode` command-line tool, so controller verification and an air
run are still required before cutting material.

## Initial Version Warning

This manual and the app describe an initial version. A lot of bugs can exist.

The project was vibecoded, and code quality or correctness was not the primary concern during
development. You **must** double-check generated NC files, preview output, tool lists, controller
behavior, and machine setup before running a CNC job.

## Start the App

Install and run the app as described in the project [README](../README.md):

```bash
.venv/bin/python main.py
```

or:

```bash
.venv/bin/pcb2gcode-ui
```

The main window opens directly into the working interface.

![Main window with file inputs and grouped options](screenshots/main%2C%20initial.png)

## Normal Workflow

1. Open an existing `millproject`, or select the input files manually.
2. Select the front, back, drill, and outline files needed for the job.
3. Confirm or change the output directory.
4. Select a predefined profile if one matches the machine workflow.
5. Adjust options in the grouped tabs.
6. Use Preview to inspect Gerber, drill, outline, and existing/generated NC files.
7. Use Validate to run `pcb2gcode` parameter validation without exporting NC files.
8. Use Generate NC to validate again and create output files.
9. Inspect the command history, preview, and generated tool report before running the CNC job.

## Toolbar

The top toolbar contains the main project and execution actions:

- Open: load a `millproject` file.
- Save: save the current settings to the loaded `millproject`.
- Save as: write the current settings to a new `millproject`.
- Validate: run local validation and `pcb2gcode --no-export`.
- Preview: open the preview window.
- Help: open in-app usage notes.
- Generate NC: validate and generate NC files in the output directory.

`Generate NC` is right-aligned because it performs the main output operation.

## Input Files

The file section contains:

- Front: top copper Gerber.
- Back: bottom copper Gerber.
- Drill: source Excellon drill file.
- Outline: board outline or cutoff Gerber.
- Output directory: where generated NC files and reports are written.

The output directory defaults to `nc/` next to the first selected input file. You can override it
with the directory picker. The app creates the directory when needed and may overwrite output files
with the same configured names.

## Profiles

Profiles are predefined option sets stored in the repository. Select a profile from the main
interface when you want fixed machine-specific behavior.

![Profile selector in the main interface](screenshots/main%2C%20profiles.png)

Profile options are locked in the UI and cannot be edited while the profile is active. The selected
profile name is saved in the app settings, so the same profile is restored on the next launch.

The included `MaxMake` profile enables these post-processing options:

- Remove tool commands matching `T*`.
- Insert `G00 X0.00000 Y0.00000` before `M3`.

This profile is intended for workflows where the CNC moves the tool to a probe position after a
tool change, and returning to work Z before moving to origin would be unsafe.

For MaxMake HiMill D1S setup and two-sided operation details, see
[MaxMake HiMill D1S](cnc/maxmake-himill-d1s.md).

## Grouped Options

Options are grouped by purpose in tabs, including generic machine settings, CNC heights, milling,
drilling, outline cutting, optimization, autolevelling, alignment, pre-processing, post-processing,
and output filenames.

Each option has a compact help button. Use it when the effect of a `pcb2gcode` option is unclear.
The app validates obvious local mistakes first, then asks `pcb2gcode` to validate the full command.

## Alignment Drill Pre-processing

The pre-processing section can generate a separated two-hole alignment drill source file. This is
used for double-sided boards where the board must be flipped and realigned.

![Alignment drill pre-processing options](screenshots/main%2C%20allign%20preprocessor.png)

When alignment drill pre-processing is enabled, the app:

- Runs a temporary `pcb2gcode` pass to get outline geometry.
- Calculates the alignment offset from the outline/cutoff bounds.
- Writes a separated two-hole Excellon alignment drill source file.
- Fills the alignment drill source field after pre-processing.
- During generation, creates a separated front-side alignment drill NC file.

The alignment drill NC generation overrides only the drill-specific parameters needed for this
separate run: drill input file, drill output file, drill depth, drill side, and drill diameters.
The alignment drill side is front.

## Preview

Open Preview before generation to inspect the source layout. The preview can show Gerber layers,
drill hits, outline/cutoff geometry, an optional auxiliary Gerber, and generated NC movement.

![Gerber preview with board layers](screenshots/preview%2C%20gerber.png)

The preview uses one shared coordinate system. Alignment offsets move Gerber, drill, outline, and
auxiliary source artwork. Loaded NC files remain in their generated coordinates. This makes it
possible to compare source files against generated output.

Use the preview controls to:

- Switch front/back viewing side.
- Adjust active-side transparency.
- Toggle Gerber layers.
- Toggle NC output groups.
- Load an auxiliary Gerber for visual comparison.
- Refresh after changing files or generating NC.

![Combined Gerber and NC preview](screenshots/preview%2C%20all%20layours.png)

## NC Tool Table

When NC files are visible, the preview overlays a tool table. The table is grouped by NC file, so
front, back, drill, alignment drill, milldrill, and outline output can be checked separately.

![NC-only preview with coordinate axes and tool table](screenshots/preview%2C%20only%20NC%2C%20coordinate%20axis%20and%20tool%20table.png)

Each NC file also gets its own coordinate axis. Use these axes to confirm that origin and direction
match the expected machine setup.

The preview is a visual inspection aid. It draws supported linear movement and tool groups, but it
does not simulate every controller command.

## Command Output and History

The command output panel keeps history for external tool runs and internal processing steps. It
includes:

- The `pcb2gcode` command line used for validation and generation.
- `stdout` and `stderr` from external tool runs.
- Pre-processing messages.
- Post-processing messages.
- Generated report messages.

Use this panel first when output is missing or a command fails. It should show the exact failing
command and the error reported by `pcb2gcode`.

## Generated Files

Generated files are written to the selected output directory. The exact NC filenames come from the
output options, such as front, back, drill, alignment drill, milldrill, and outline output names.

The app also writes `tools.md` to the output directory after generation. This report lists tools by
NC file, matching the preview tool table grouping. Use it as a quick setup checklist before loading
files into the CNC controller.

## Practical Safety Checks

Before running a generated file on the CNC:

- Confirm the selected profile and locked options are intended for the current machine.
- Confirm the output directory contains fresh files from the latest generation run.
- Confirm front/back side, origin, and mirror behavior in Preview.
- Confirm alignment drill output is front-side only when using the alignment drill workflow.
- Confirm tool diameters and depths in `tools.md`.
- Read the command output history for warnings.
- Run controller verification or an air run before cutting material.
