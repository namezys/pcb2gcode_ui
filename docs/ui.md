# UI Decisions

## Purpose

The app is a fast parameter editor for `pcb2gcode`, not a replacement for the command-line
tool. It keeps the workflow focused on loading or creating a `millproject`, selecting input
files, validating parameters, and generating NC files.

## Layout

The first screen is the working UI:

- Toolbar: open, save, save as, validate, and generate.
- File section: `front`, `back`, `drill`, `outline`, and output directory pickers.
- Preview button: opens a closable preview window before NC generation.
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

## Preview

The Preview toolbar button opens a closable dialog and forces a refresh. The preview uses
PyGerber's Python API (`pygerber.gerberx3.api.v2`) to parse and rasterize Gerber layers in
memory at high density. The app composes the PNG with Pillow and shows it directly in Flet,
without invoking the PyGerber CLI or writing preview files.

The preview window uses two compact control rows. The first row has the front/back view selector,
transparency slider, Load Aux button, and Regenerate button. The second row has horizontal
visibility toggles for front, back, drill, cutoff/outline, and Aux. Aux is one preview-only
Gerber file and is not saved to `millproject`.

All enabled layers are composed into one shared board coordinate system. Front copper is tinted
green/cyan, back copper amber/orange, cutoff light gray, Aux blue, and drill hits light blue.
Preview layers are not mirrored; mirror-related options are left to `pcb2gcode` generation.

Preview transforms follow the pcb2gcode options that affect placement: `metric`, `x-offset`,
`y-offset`, `zero-start`, `tile-x`, and `tile-y`. Drill rendering uses a narrow preview-only Excellon reader for common decimal
`METRIC`/`INCH` files with `TnnCdiameter` tools and `X...Y...` hits. Unsupported drill syntax is
reported as a preview warning and does not affect validation or NC generation.

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
