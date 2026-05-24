from dataclasses import dataclass, field
from pathlib import Path

CHOICE_BOOL_TRUE = {"1", "true", "yes", "on"}
CHOICE_BOOL_FALSE = {"0", "false", "no", "off"}
FILE_OPTIONS = {"front", "back", "drill", "outline"}
OUTPUT_FILE_OPTIONS = {
    "front-output",
    "back-output",
    "drill-output",
    "milldrill-output",
    "outline-output",
}


@dataclass(frozen=True)
class OptionSpec:
    key: str
    group: str
    label: str
    kind: str
    help_text: str
    default: str = ""
    choices: tuple[str, ...] = field(default_factory=tuple)


OPTION_SPECS: tuple[OptionSpec, ...] = (
    OptionSpec(
        "ignore-warnings", "Generic", "Ignore warnings", "bool", "Ignore warnings.", "false"
    ),
    OptionSpec(
        "metric", "Generic", "Metric input", "bool", "Use metric units for parameters.", "false"
    ),
    OptionSpec(
        "metricoutput", "Generic", "Metric output", "bool", "Use metric units for output.", "false"
    ),
    OptionSpec("tolerance", "Generic", "Tolerance", "number", "Maximum toolpath tolerance."),
    OptionSpec("output-dir", "Generic", "Output directory", "directory", "Output directory."),
    OptionSpec("basename", "Generic", "Basename", "text", "Prefix for default output file names."),
    OptionSpec("sanity-checks", "Generic", "Sanity checks", "bool", "Run sanity checks.", "false"),
    OptionSpec(
        "single-thread", "Generic", "Single thread", "bool", "Disable multi-threading.", "false"
    ),
    OptionSpec("front", "Files", "Front Gerber", "file", "Front side RS274-X .gbr."),
    OptionSpec("back", "Files", "Back Gerber", "file", "Back side RS274-X .gbr."),
    OptionSpec("drill", "Files", "Drill file", "file", "Excellon drill file."),
    OptionSpec("outline", "Files", "Outline Gerber", "file", "PCB outline polygon RS274-X .gbr."),
    OptionSpec("zsafe", "CNC", "Safe Z", "number", "Safety height during rapid moves."),
    OptionSpec(
        "spinup-time", "CNC", "Spin-up time", "number", "Time for spindle to reach speed.", "1ms"
    ),
    OptionSpec("spindown-time", "CNC", "Spin-down time", "number", "Time for spindle to stop."),
    OptionSpec("zchange", "CNC", "Tool-change Z", "number", "Tool changing height."),
    OptionSpec(
        "zchange-absolute", "CNC", "Z change absolute", "bool", "Use G53 machine height.", "false"
    ),
    OptionSpec("nog64", "CNC", "No G64", "bool", "Do not set an explicit G64.", "false"),
    OptionSpec(
        "nog91-1", "CNC", "No G91.1", "bool", "Do not set G91.1 in drill headers.", "false"
    ),
    OptionSpec("nog81", "CNC", "No G81", "bool", "Replace G81 with G0 and G1.", "false"),
    OptionSpec("nom6", "CNC", "No M6", "bool", "Do not emit M6 on tool changes.", "false"),
    OptionSpec("tile-x", "CNC", "Tile columns", "integer", "Number of tiling columns.", "1"),
    OptionSpec("tile-y", "CNC", "Tile rows", "integer", "Number of tiling rows.", "1"),
    OptionSpec("voronoi", "Milling", "Voronoi", "bool", "Generate voronoi regions.", "false"),
    OptionSpec("offset", "Milling", "Offset", "number", "Extra offset added to all traces.", "0"),
    OptionSpec(
        "mill-diameters",
        "Milling",
        "Mill diameters",
        "text",
        "Comma-separated mill bit diameters.",
        "0",
    ),
    OptionSpec(
        "milling-overlap",
        "Milling",
        "Milling overlap",
        "text",
        "Overlap passes, percent or length.",
        "50%",
    ),
    OptionSpec(
        "isolation-width",
        "Milling",
        "Isolation width",
        "number",
        "Minimum copper isolation width.",
        "0",
    ),
    OptionSpec("zwork", "Milling", "Work Z", "number", "Milling depth while engraving."),
    OptionSpec("mill-feed", "Milling", "Mill feed", "number", "Feed while isolating."),
    OptionSpec(
        "mill-vertfeed", "Milling", "Mill vertical feed", "number", "Vertical feed while isolating."
    ),
    OptionSpec(
        "mill-infeed", "Milling", "Mill infeed", "number", "Maximum milling depth per pass."
    ),
    OptionSpec("mill-speed", "Milling", "Mill speed", "number", "Spindle RPM when milling."),
    OptionSpec(
        "mill-feed-direction",
        "Milling",
        "Mill feed direction",
        "choice",
        "Direction for milling paths.",
        "any",
        ("any", "climb", "conventional"),
    ),
    OptionSpec(
        "invert-gerbers",
        "Milling",
        "Invert Gerbers",
        "bool",
        "Invert front/back polarity.",
        "false",
    ),
    OptionSpec(
        "draw-gerber-lines", "Milling", "Draw Gerber lines", "bool", "Draw lines as lines.", "false"
    ),
    OptionSpec(
        "preserve-thermal-reliefs",
        "Milling",
        "Thermal reliefs",
        "bool",
        "Preserve thermal reliefs.",
        "true",
    ),
    OptionSpec(
        "front-output",
        "Output",
        "Front output",
        "text",
        "Output file for front layer.",
        "front.ngc",
    ),
    OptionSpec(
        "back-output", "Output", "Back output", "text", "Output file for back layer.", "back.ngc"
    ),
    OptionSpec(
        "milldrill-diameter",
        "Drilling",
        "Milldrill diameter",
        "number",
        "End mill diameter for milldrilling.",
    ),
    OptionSpec(
        "min-milldrill-hole-diameter",
        "Drilling",
        "Min milldrill hole",
        "number",
        "Minimum hole width for milldrilling.",
    ),
    OptionSpec("zdrill", "Drilling", "Drill Z", "number", "Drilling depth."),
    OptionSpec("zmilldrill", "Drilling", "Milldrill Z", "number", "Milldrilling depth."),
    OptionSpec("drill-feed", "Drilling", "Drill feed", "number", "Drill feed."),
    OptionSpec("drill-speed", "Drilling", "Drill speed", "number", "Spindle RPM when drilling."),
    OptionSpec(
        "drill-side",
        "Drilling",
        "Drill side",
        "choice",
        "Drill side.",
        "auto",
        ("auto", "front", "back"),
    ),
    OptionSpec(
        "drills-available", "Drilling", "Drills available", "text", "List of available drills."
    ),
    OptionSpec(
        "onedrill", "Drilling", "One drill", "bool", "Use only one drill bit size.", "false"
    ),
    OptionSpec(
        "drill-output", "Output", "Drill output", "text", "Output file for drilling.", "drill.ngc"
    ),
    OptionSpec(
        "milldrill-output",
        "Output",
        "Milldrill output",
        "text",
        "Output file for milldrilling.",
        "milldrill.ngc",
    ),
    OptionSpec(
        "fill-outline", "Outline", "Fill outline", "bool", "Accept contour as outline.", "true"
    ),
    OptionSpec(
        "cutter-diameter", "Outline", "Cutter diameter", "number", "End mill diameter for cutting."
    ),
    OptionSpec("zcut", "Outline", "Cut Z", "number", "PCB cutting depth."),
    OptionSpec("cut-feed", "Outline", "Cut feed", "number", "PCB cutting feed."),
    OptionSpec(
        "cut-vertfeed", "Outline", "Cut vertical feed", "number", "PCB vertical cutting feed."
    ),
    OptionSpec("cut-speed", "Outline", "Cut speed", "number", "Spindle RPM when cutting."),
    OptionSpec("cut-infeed", "Outline", "Cut infeed", "number", "Maximum cutting depth per pass."),
    OptionSpec(
        "cut-side",
        "Outline",
        "Cut side",
        "choice",
        "Cut side.",
        "auto",
        ("auto", "front", "back"),
    ),
    OptionSpec("bridges", "Outline", "Bridges", "number", "Bridge width for outline cut.", "0"),
    OptionSpec("bridgesnum", "Outline", "Bridge count", "integer", "Number of bridges.", "2"),
    OptionSpec("zbridges", "Outline", "Bridge Z", "number", "Bridge height."),
    OptionSpec(
        "outline-output",
        "Output",
        "Outline output",
        "text",
        "Output file for outline.",
        "outline.ngc",
    ),
    OptionSpec(
        "optimise",
        "Optimization",
        "Optimise",
        "number",
        "Reduce output size and precision.",
        "0.0001in",
    ),
    OptionSpec(
        "eulerian-paths",
        "Optimization",
        "Eulerian paths",
        "bool",
        "Avoid milling same path twice.",
        "true",
    ),
    OptionSpec(
        "vectorial", "Optimization", "Vectorial", "bool", "Enable vectorial rendering.", "true"
    ),
    OptionSpec("tsp-2opt", "Optimization", "TSP 2OPT", "bool", "Find faster toolpaths.", "true"),
    OptionSpec(
        "path-finding-limit",
        "Optimization",
        "Path finding limit",
        "integer",
        "Path-finding search steps.",
        "1",
    ),
    OptionSpec(
        "g0-vertical-speed",
        "Optimization",
        "G0 vertical speed",
        "number",
        "Vertical G0 speed.",
        "50in/min",
    ),
    OptionSpec(
        "g0-horizontal-speed",
        "Optimization",
        "G0 horizontal speed",
        "number",
        "Horizontal G0 speed.",
        "100in/min",
    ),
    OptionSpec(
        "backtrack", "Optimization", "Backtrack", "number", "Allowed retracing speed.", "inf"
    ),
    OptionSpec(
        "al-front",
        "Autolevelling",
        "Autolevel front",
        "bool",
        "Enable front autoleveller.",
        "false",
    ),
    OptionSpec(
        "al-back", "Autolevelling", "Autolevel back", "bool", "Enable back autoleveller.", "false"
    ),
    OptionSpec(
        "software",
        "Autolevelling",
        "Software",
        "choice",
        "Destination software for autolevelling.",
        "",
        ("linuxcnc", "mach3", "mach4", "custom"),
    ),
    OptionSpec("al-x", "Autolevelling", "Probe X", "number", "Max X distance between probes."),
    OptionSpec("al-y", "Autolevelling", "Probe Y", "number", "Max Y distance between probes."),
    OptionSpec("al-probefeed", "Autolevelling", "Probe feed", "number", "Probe feed speed."),
    OptionSpec(
        "al-probe-on",
        "Autolevelling",
        "Probe on",
        "text",
        "Commands to enable probe.",
        "(MSG, Attach the probe tool)@M0 ( Temporary machine stop. )",
    ),
    OptionSpec(
        "al-probe-off",
        "Autolevelling",
        "Probe off",
        "text",
        "Commands to disable probe.",
        "(MSG, Detach the probe tool)@M0 ( Temporary machine stop. )",
    ),
    OptionSpec("al-probecode", "Autolevelling", "Probe code", "text", "Custom probe code.", "G31"),
    OptionSpec(
        "al-probevar",
        "Autolevelling",
        "Probe variable",
        "integer",
        "Variable storing probe result.",
        "2002",
    ),
    OptionSpec(
        "al-setzzero", "Autolevelling", "Set Z zero", "text", "G-code for setting Z zero.", "G92 Z0"
    ),
    OptionSpec("x-offset", "Alignment", "X offset", "number", "Origin offset on X axis.", "0"),
    OptionSpec("y-offset", "Alignment", "Y offset", "number", "Origin offset on Y axis.", "0"),
    OptionSpec(
        "zero-start", "Alignment", "Zero start", "bool", "Set project start at (0,0).", "false"
    ),
    OptionSpec(
        "mirror-axis", "Alignment", "Mirror X axis", "number", "Two-sided flip axis x=VALUE.", "0"
    ),
    OptionSpec("mirror-yaxis", "Alignment", "Mirror Y axis", "bool", "Flip along Y axis.", "false"),
)

SPEC_BY_KEY = {spec.key: spec for spec in OPTION_SPECS}


def default_values() -> dict[str, str]:
    return {spec.key: spec.default for spec in OPTION_SPECS}


def bool_value(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in CHOICE_BOOL_TRUE:
        return True
    if normalized in CHOICE_BOOL_FALSE:
        return False
    raise ValueError(f"Expected boolean value, got {value!r}")


def first_input_directory(values: dict[str, str]) -> Path:
    for key in ("front", "back", "drill", "outline"):
        value = values.get(key, "").strip()
        if value:
            return Path(value).expanduser().resolve().parent
    return Path.cwd()


def default_output_directory(values: dict[str, str]) -> Path:
    return first_input_directory(values) / "nc"
