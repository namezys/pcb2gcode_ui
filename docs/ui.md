# UI Decisions

## Purpose

The app is a fast parameter editor for `pcb2gcode`, not a replacement for the command-line
tool. It keeps the workflow focused on loading or creating a `millproject`, selecting input
files, validating parameters, and generating NC files.

## Layout

The first screen is the working UI:

- Toolbar: open, save, save as, validate, and generate.
- File section: `front`, `back`, `drill`, `outline`, and output directory pickers.
- Parameter tabs: Generic, CNC, Milling, Drilling, Outline, Optimization, Autolevelling,
  Alignment, and Output.
- Command output panel for validation and generation logs.

Each parameter control includes tooltip help based on the official `pcb2gcode --help` text and
the bundled `pcb2gcode` source metadata.

## Millproject Files

Loaded `millproject` files are parsed as `key=value` lines. Blank lines, comments, unknown keys,
deprecated options, and custom pre/post-processing options are not preserved. Saving rewrites a
clean canonical file grouped by UI section.

Absolute input and output paths are written relative to the saved `millproject` directory when
they are inside that directory. Command execution resolves relative paths against the loaded
`millproject` directory so validation can run safely from a temporary working directory.

## Validation

The app validates obvious local rules first: booleans, choices, numeric values, required fields,
and known incompatible combinations. It then asks `pcb2gcode` to validate the full parameter set
with `--noconfigfile --no-export` from a temporary directory. This avoids polluting the project
root because `pcb2gcode` can still write SVG preview files when NC export is disabled.

## Generation

Generation always runs validation first. The app passes parameters directly to the installed
`pcb2gcode` binary and sets `--output-dir` to the selected directory. Standard output file
parameters such as `front-output`, `back-output`, `drill-output`, `milldrill-output`, and
`outline-output` control the generated NC filenames.
