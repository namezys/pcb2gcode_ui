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
- Help button: opens workflow, safety, validation, and preview guidance.
- Parameter tabs: Generic, CNC, Milling, Drilling, Outline, Optimization, Autolevelling,
  Alignment, and Output.
- Command output panel for validation and generation logs.

Each parameter control keeps a short tooltip and has a compact `?` button. The button opens a
scrollable Markdown help dialog with option type/default notes, G-code effect, practical usage
notes, and source references extracted from `docs/detail help.md`. Help content lives in a
separate Python data module so the UI layout code stays focused on controls.

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

The preview window uses compact control rows. The first row has the front/back view selector,
transparency slider, Aux loader, NC loader, Refresh button, and Help button. The second row starts
with `Gerber:` and has horizontal visibility toggles for front, back, drill, cutoff/outline, and
Aux. Aux is one preview-only Gerber file and is not saved to `millproject`. The third row starts
with `NC:` and toggles G-code movement preview by output type after the NC files are loaded.

Preview Help opens a dialog that explains every preview control and includes a color legend table
with real preview-color swatches for Gerber layers, drill hits, cutoff, Aux, G-code cuts, and
retract/travel moves.

All enabled layers are composed into one shared board coordinate system. Front copper is tinted
green/cyan, back copper red/pink, cutoff light gray, Aux blue, and drill hits light blue. The
front/back selector controls the viewing side, not which layers are loaded. In front view the
paint order is back, front, drill, cutoff, Aux. In back view the paint order is front, back,
drill, cutoff, Aux, and the entire composed layout is mirrored horizontally.

The transparency slider applies only to the active copper side and drill hits: front plus drill
in front view, back plus drill in back view. The inactive copper side, cutoff, and Aux stay fully
opaque so reference geometry remains readable.

Preview transforms follow the pcb2gcode options that affect input-source placement: `metric`,
`x-offset`, `y-offset`, `zero-start`, `tile-x`, and `tile-y`. The alignment offsets move Gerber,
drill, cutoff, and Aux source artwork against generated NC output; loaded NC files stay in their
already-generated coordinates. Mirror-related pcb2gcode generation options are not applied
directly; the back preview side uses its own horizontal view mirror.

Drill rendering uses a narrow preview-only Excellon reader for common decimal and implied-decimal
`METRIC`/`INCH` files with `TnnCdiameter` tools and `X...Y...` hits. Cutoff rendering first uses
PyGerber; if PyGerber rejects a simple EAGLE-style profile, the app falls back to a line-segment
RS-274X reader for circular-aperture `D02`/`D01` outlines. Unsupported preview syntax is reported
as a warning and does not affect validation or NC generation.

G-code preview reads configured output files from the output directory using `gcodeparser` plus a
small local movement interpreter. It draws only linear `G0`/`G1` traces: a segment is a cut when
either endpoint has `Z < 0`; otherwise it is a retract/travel move. Cut lines are solid;
retract/travel lines are dotted. The preview colors paths by active tool id per NC file and
mirrors back NC output the same way as the back Gerber layer. It overlays a tool table for active
NC files, including separated alignment drill output when align drills are enabled. Each loaded
NC file also gets its own origin axis with labeled positive X and Y
directions. The preview bounds are calculated from all configured Gerber/drill/Aux files and
loaded NC files, so toggling layer checkboxes does not resize the image. The tool table labels
each NC file group and omits tools that contain only pass/retract moves. See
[gcode-preview.md](gcode-preview.md) for the supported subset.

## Validation

The app validates obvious local rules first: booleans, choices, numeric values, required fields,
and known incompatible combinations. It then asks `pcb2gcode` to validate the full parameter set
with `--noconfigfile --no-export` from a temporary directory. This avoids polluting the project
root because `pcb2gcode` can still write SVG preview files when NC export is disabled.

## Generation

Generation always runs validation first. The app passes parameters directly to the installed
`pcb2gcode` binary and sets `--output-dir` to the selected directory. Standard output file
parameters such as `front-output`, `back-output`, `drill-output`, `milldrill-output`, and
`outline-output` control the generated NC filenames. When Align drills is enabled, the UI also
writes `pre-align-drill-source` and generates `pre-align-drill-output` with a separated front-side
drill run that uses the calculated alignment offsets.
