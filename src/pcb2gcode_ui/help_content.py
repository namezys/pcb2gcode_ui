from dataclasses import dataclass


@dataclass(frozen=True)
class OptionHelp:
    key: str
    title: str
    type_default: str
    gcode_effect: str
    details: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class GeneralHelp:
    title: str
    markdown: str


@dataclass(frozen=True)
class PreviewColorLegendEntry:
    label: str
    color: str
    meaning: str


SOURCE_MAN = "current pcb2gcode man page"
SOURCE_GENERIC = "Generic wiki"
SOURCE_COMMON = "Common wiki"
SOURCE_MILLING = "Milling wiki"
SOURCE_DRILLING = "Drilling wiki"
SOURCE_OUTLINE = "Outline wiki"
SOURCE_ALIGNMENT = "Alignment wiki"
SOURCE_OPTIMIZATION = "Optimizations wiki"
SOURCE_OBSOLETE_MANUAL = "legacy/manual notes"
SOURCE_DETAIL_HELP = "docs/detail help.md"
SOURCE_LOCAL_UI = "local UI option"

GENERAL_HELP = GeneralHelp(
    title="PCB2GCode UI Help",
    markdown=(
        "## Recommended workflow\n\n"
        "1. Open an existing `millproject` or select board files directly.\n"
        "2. Select front/back Gerber, drill Excellon, and outline Gerber inputs.\n"
        "3. Use **Preview** to inspect layer alignment, side view, drill positions, cutoff, "
        "and optional Aux reference geometry.\n"
        "4. Adjust grouped pcb2gcode options, then save the `millproject`.\n"
        "5. Run **Validate** before cutting.\n"
        "6. Run **Generate NC** to write output files into the selected output directory. "
        "Optional UI pre-process steps run before pcb2gcode; post-process steps run after "
        "successful generation.\n\n"
        "## Project files\n\n"
        "`millproject` is the stable place for machine/job settings. Keep cutter diameters, "
        "feeds, speeds, safe heights, controller flags, and output filenames there. Board file "
        "paths can be changed per job. The output directory defaults to `nc/` next to the first "
        "selected input file.\n\n"
        "## Safety-critical checks\n\n"
        "Always review `zsafe`, `zchange`, spindle dwell, feed rates, spindle speeds, cutting "
        "depths, `cut-infeed`, and bridges before running a machine. For GRBL-like controllers, "
        "`nog81`, `nom6`, and sometimes `nog64` are common compatibility switches.\n\n"
        "## Preview limits\n\n"
        "Preview is visual guidance. It uses PyGerber plus local drill/cutoff readers and follows "
        "the UI preview rules. The installed `pcb2gcode` binary remains the source of truth for "
        "generated NC files, so inspect and air-run generated G-code before cutting stock."
    ),
)

PREVIEW_HELP = GeneralHelp(
    title="Preview Help",
    markdown=(
        "## Controls\n\n"
        "- **Front / Back selector**: chooses the viewing side. Back view mirrors the composed "
        "layout horizontally so it is easier to compare with back-side machining.\n"
        "- **Transparency slider**: controls opacity for the active copper side and drill hits "
        "only. Reference layers remain opaque.\n"
        "- **Aux**: loads one preview-only Gerber reference layer. It is not saved to the "
        "`millproject`.\n"
        "- **NC**: reads generated NC files from the configured output directory.\n"
        "- **Refresh**: rerenders the preview from the current files and settings.\n"
        "- **Gerber row Front / Back / Drill / Cutoff / Aux**: show or hide Gerber, drill, "
        "outline, and preview-only Aux layers.\n"
        "- **NC row Front / Back / Drill / Milldrill / Outline**: choose which "
        "loaded NC output traces are visible.\n\n"
        "## Notes\n\n"
        "Gerber, drill, cutoff, Aux, and G-code traces are drawn in one shared coordinate "
        "system. Preview follows placement-related settings such as metric input, offsets, "
        "zero-start, and tiling. G-code preview is a visual aid: it currently draws linear "
        "`G0`/`G1` movement only, treats a segment as a cut when either endpoint has "
        "`Z < 0`, colors paths by active tool id per NC file, and keeps generated NC files as "
        "the source of truth. Each loaded NC file also gets its own origin axis with `X+` and "
        "`Y+` labels. The overlay table omits tools with only pass/retract moves."
    ),
)

PREVIEW_COLOR_LEGEND: tuple[PreviewColorLegendEntry, ...] = (
    PreviewColorLegendEntry("Front copper", "#23DC96", "Front Gerber copper layer."),
    PreviewColorLegendEntry("Back copper", "#E84A5F", "Back Gerber copper layer."),
    PreviewColorLegendEntry("Drill hit fill", "#57B2FF", "Excellon drill circle fill."),
    PreviewColorLegendEntry("Drill hit outline", "#DCF5FF", "Excellon drill circle edge."),
    PreviewColorLegendEntry("Cutoff / outline Gerber", "#EBEEF2", "Board outline/cutoff Gerber."),
    PreviewColorLegendEntry("Aux Gerber", "#5096FF", "Preview-only auxiliary Gerber."),
    PreviewColorLegendEntry("Front G-code cuts", "#FFD64E", "Cutting moves from front NC output."),
    PreviewColorLegendEntry("Back G-code cuts", "#FF6987", "Cutting moves from back NC output."),
    PreviewColorLegendEntry("Drill G-code cuts", "#5AD2FF", "Cutting moves from drill NC output."),
    PreviewColorLegendEntry(
        "Align drill G-code cuts",
        "#96B9FF",
        "Cutting moves from separated alignment drill NC output.",
    ),
    PreviewColorLegendEntry(
        "Milldrill G-code cuts",
        "#60D394",
        "Cutting moves from milldrill NC output.",
    ),
    PreviewColorLegendEntry("Outline G-code cuts", "#FFFFFF", "Cutting moves from outline NC."),
    PreviewColorLegendEntry("Retract / travel G-code", "#AAB2B8", "Low-alpha non-cutting moves."),
    PreviewColorLegendEntry("NC X+ axis", "#FF5C5C", "Positive X direction for each NC file."),
    PreviewColorLegendEntry("NC Y+ axis", "#5FDC78", "Positive Y direction for each NC file."),
)


def option_help_markdown(help_entry: OptionHelp) -> str:
    sources = "\n".join(f"- {source}" for source in help_entry.sources)
    return (
        f"## `{help_entry.key}`\n\n"
        f"**Type/default:** {help_entry.type_default}\n\n"
        f"**G-code effect:** {help_entry.gcode_effect}\n\n"
        f"{help_entry.details}\n\n"
        "## Sources\n\n"
        f"{sources}"
    )


def _entry(
    key: str,
    title: str,
    type_default: str,
    gcode_effect: str,
    details: str,
    sources: tuple[str, ...],
) -> OptionHelp:
    return OptionHelp(key, title, type_default, gcode_effect, details, sources)


OPTION_HELP_BY_KEY: dict[str, OptionHelp] = {
    "ignore-warnings": _entry(
        "ignore-warnings",
        "Ignore warnings",
        "bool, default `false`",
        "None.",
        "Continue despite parser or path warnings. Use this only after inspecting the warning "
        "and generated output; it is a debugging escape hatch, not a normal safety setting.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "metric": _entry(
        "metric",
        "Metric input",
        "bool, default `false`",
        "None directly.",
        "Interpret option values as metric unless a value has an explicit unit suffix. This "
        "does not change emitted G-code units; use `metricoutput` for that.",
        (SOURCE_GENERIC, SOURCE_DETAIL_HELP),
    ),
    "metricoutput": _entry(
        "metricoutput",
        "Metric output",
        "bool, default `false`",
        "Controls output units, typically `G21` instead of `G20`.",
        "Emit metric G-code coordinates and feeds. Keep this explicit so controller setup and "
        "generated file units are obvious.",
        (SOURCE_GENERIC, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "tolerance": _entry(
        "tolerance",
        "Tolerance",
        "length, default unspecified by current docs",
        "Controls toolpath tolerance and LinuxCNC-style `G64 P...` unless suppressed.",
        "Modern replacement for the older deprecated `g64` distance option. Larger tolerance can "
        "simplify paths but may reduce geometric fidelity.",
        (SOURCE_MAN, SOURCE_GENERIC, SOURCE_DETAIL_HELP),
    ),
    "nog64": _entry(
        "nog64",
        "No G64",
        "bool, default `false`",
        "Suppresses explicit `G64` path blending output.",
        "Enable for controllers that reject or ignore `G64`. Leave off when LinuxCNC-style path "
        "blending with `tolerance` is desired.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "output-dir": _entry(
        "output-dir",
        "Output directory",
        "path, default unspecified by pcb2gcode",
        "None; changes where files are written.",
        "Directory for generated NC files. The UI defaults it to `nc/` next to the first selected "
        "input file, and generation overwrites pcb2gcode outputs in that directory.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "basename": _entry(
        "basename",
        "Basename",
        "string, default unspecified by current docs",
        "None; affects autogenerated output names.",
        "Base name used when pcb2gcode derives output filenames. Explicit output filename options "
        "are clearer when you need stable file names.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "sanity-checks": _entry(
        "sanity-checks",
        "Sanity checks",
        "bool, default `false`",
        "None directly.",
        "Passes pcb2gcode's sanity-check option through when enabled. Use validation and preview "
        "first; this is a pcb2gcode-level check, not a replacement for machine review.",
        (SOURCE_LOCAL_UI,),
    ),
    "post-remove-t": _entry(
        "post-remove-t",
        "Remove T*",
        "bool, default `false`",
        "Comments generated lines containing `T` followed by digits.",
        "UI-only post-processing step run after successful NC generation. Enable it for "
        "controllers that do not want standalone tool-select lines or `Tn M6` tool-change "
        "lines to execute. Matching commands are preserved as `(PP: remove ...)` comments.",
        (SOURCE_LOCAL_UI,),
    ),
    "pre-align-drills": _entry(
        "pre-align-drills",
        "Align drills",
        "bool, default `false`",
        "Generates a separated alignment drill source and NC output.",
        "UI-only pre-processing step. When enabled, the original Excellon drill file stays "
        "unchanged. The UI writes a two-hole generated drill source into the output directory "
        "and then runs a separated front-side drill command for that source.",
        (SOURCE_LOCAL_UI,),
    ),
    "pre-align-drill-diameter": _entry(
        "pre-align-drill-diameter",
        "Align drill diameter",
        "length, no default",
        "Sets the diameter for the generated alignment-drill tool.",
        "Required when Align drills is enabled. Use a real bit diameter accepted by the "
        "machine, for example `0.8mm` or `0.031in`. Values without a suffix follow the Metric "
        "input setting.",
        (SOURCE_LOCAL_UI,),
    ),
    "pre-align-drill-depth": _entry(
        "pre-align-drill-depth",
        "Align drill depth",
        "length, no default",
        "Sets the depth for the separated alignment drill NC file.",
        "Required when Align drills is enabled. Enter the depth magnitude; positive values are "
        "converted to negative drilling Z for the separated front-side alignment drill run.",
        (SOURCE_LOCAL_UI,),
    ),
    "pre-align-drill-output": _entry(
        "pre-align-drill-output",
        "Align drill output",
        "path, default `align-drill.ngc`",
        "Names the separated alignment drill NC output file.",
        "UI-only option used to run the alignment drill source separately from the main drill "
        "file. The output is generated explicitly on the front side and uses the calculated "
        "alignment offsets.",
        (SOURCE_LOCAL_UI,),
    ),
    "pre-align-drill-source": _entry(
        "pre-align-drill-source",
        "Align drill source",
        "path, generated",
        "Shows the generated two-hole Excellon alignment source.",
        "Pre-processing fills this field with the generated source path. Existing arbitrary "
        "paths are replaced by the generated path instead of being overwritten.",
        (SOURCE_LOCAL_UI,),
    ),
    "single-thread": _entry(
        "single-thread",
        "Single thread",
        "bool, default `false`",
        "None; affects generation behavior/performance.",
        "Disable pcb2gcode multi-threading. Useful for reproducible debugging or machines where "
        "parallel processing causes resource pressure.",
        (SOURCE_LOCAL_UI,),
    ),
    "front": _entry(
        "front",
        "Front Gerber",
        "file, no default",
        "Enables front copper isolation generation.",
        "Front copper RS-274X Gerber input. Use with milling depth/feed/speed settings. For "
        "two-sided jobs, keep alignment settings deliberate and preview before cutting.",
        (SOURCE_MILLING, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "back": _entry(
        "back",
        "Back Gerber",
        "file, no default",
        "Enables back copper isolation generation.",
        "Back copper RS-274X Gerber input. Back-side output can interact with side selection, "
        "offsets, zero-start, and mirror settings, so inspect generated coordinates.",
        (SOURCE_MILLING, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "drill": _entry(
        "drill",
        "Drill file",
        "file, no default",
        "Enables drilling output.",
        "Excellon drill input. Current docs also mention slot support where Gerbv provides it. "
        "Use `drill-side` for front/back coordinate-system control.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "outline": _entry(
        "outline",
        "Outline Gerber",
        "file, no default",
        "Enables outline/cutout generation.",
        "Outline Gerber input for board separation. Pair it with cutter diameter, cut depth, "
        "cut feeds, `cut-infeed`, and bridges for safer real cuts.",
        (SOURCE_OUTLINE, SOURCE_DETAIL_HELP),
    ),
    "zsafe": _entry(
        "zsafe",
        "Safe Z",
        "length, default unspecified by current docs",
        "Sets safe rapid height used around milling, drilling, alignment, and outline moves.",
        "One of the most safety-critical values. It must clear clamps, screws, uneven stock, and "
        "probe hardware before any rapid motion.",
        (SOURCE_COMMON, SOURCE_DETAIL_HELP),
    ),
    "spinup-time": _entry(
        "spinup-time",
        "Spin-up time",
        "duration, documented default `0.001s`",
        "Inserts spindle-start dwell with `G04 P...`.",
        "Delay after spindle start before cutting. Increase it when the spindle needs time to "
        "reach speed; entering copper too early can break small tools.",
        (SOURCE_COMMON, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "spindown-time": _entry(
        "spindown-time",
        "Spin-down time",
        "duration, default unspecified by current docs",
        "Inserts spindle-stop dwell with `G04 P...`.",
        "Delay after spindle stop. Use when the controller or spindle needs settling time before "
        "tool changes or manual intervention.",
        (SOURCE_COMMON, SOURCE_DETAIL_HELP),
    ),
    "zchange": _entry(
        "zchange",
        "Tool-change Z",
        "length, default unspecified by current docs",
        "Sets tool-change height.",
        "Usually a work-coordinate tool-change height unless `zchange-absolute` is enabled. Keep "
        "it high enough for manual changes and probe clearance.",
        (SOURCE_COMMON, SOURCE_DETAIL_HELP),
    ),
    "zchange-absolute": _entry(
        "zchange-absolute",
        "Z change absolute",
        "bool, default `false`",
        "Adds machine-coordinate `G53` behavior to tool-change motion.",
        "Use when `zchange` should be interpreted in machine coordinates rather than the active "
        "work coordinate system.",
        (SOURCE_COMMON, SOURCE_DETAIL_HELP),
    ),
    "tile-x": _entry(
        "tile-x",
        "Tile columns",
        "integer, default `1`",
        "Duplicates generated geometry along X.",
        "Number of tiled copies along X. Values below 1 are invalid. Preview applies this for "
        "visual placement.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "tile-y": _entry(
        "tile-y",
        "Tile rows",
        "integer, default `1`",
        "Duplicates generated geometry along Y.",
        "Number of tiled copies along Y. Values below 1 are invalid. Preview applies this for "
        "visual placement.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "voronoi": _entry(
        "voronoi",
        "Voronoi",
        "bool, default `false`",
        "Changes isolation geometry and can affect path planning.",
        "Route divider lines between copper regions instead of uniform offsets around every "
        "trace. Often faster, but the resulting clearance geometry is different.",
        (SOURCE_MILLING, SOURCE_DETAIL_HELP),
    ),
    "offset": _entry(
        "offset",
        "Offset",
        "length, default `0`",
        "Changes isolation geometry.",
        "Older fixed-offset way to enlarge isolation. Current guidance treats it as inferior to "
        "`isolation-width` plus `mill-diameters` for modern multi-tool workflows; it is not a "
        "reliable extra clearance layer on top of `mill-diameters`.",
        (SOURCE_MILLING, "issue #412", SOURCE_DETAIL_HELP),
    ),
    "mill-diameters": _entry(
        "mill-diameters",
        "Mill diameters",
        "comma-separated lengths, documented default `0`",
        "Controls isolation tool stages and geometry.",
        "Preferred modern multi-tool routing control. Tools are applied in sequence to improve "
        "access and cleanup. Gotcha: literal `0` is unsafe on current builds per issue evidence; "
        "use real tool diameters such as `0.20mm`.",
        (SOURCE_MILLING, "issue #749", SOURCE_DETAIL_HELP),
    ),
    "milling-overlap": _entry(
        "milling-overlap",
        "Milling overlap",
        "percent or length, default `50%`",
        "Controls overlap between adjacent isolation passes.",
        "Higher overlap improves cleanup but increases machining time. Use with "
        "`isolation-width` and real `mill-diameters`.",
        (SOURCE_MILLING, SOURCE_DETAIL_HELP),
    ),
    "isolation-width": _entry(
        "isolation-width",
        "Isolation width",
        "length, default `0`",
        "Sets target copper clearance around traces.",
        "Current wiki guidance recommends this over legacy `extra-passes`. Increase for more "
        "clearance, but expect more toolpath time.",
        (SOURCE_MILLING, SOURCE_DETAIL_HELP),
    ),
    "zwork": _entry(
        "zwork",
        "Work Z",
        "length, default unspecified by current docs",
        "Sets isolation milling depth.",
        "Target Z depth for copper isolation. Usually a shallow negative value. Pair with "
        "`mill-infeed` if multiple depth passes are needed.",
        (SOURCE_MILLING, SOURCE_DETAIL_HELP),
    ),
    "mill-feed": _entry(
        "mill-feed",
        "Mill feed",
        "speed, default unspecified by current docs",
        "Sets horizontal feed for isolation moves.",
        "Controls cutting feed while the tool is moving laterally through copper/board material.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "mill-vertfeed": _entry(
        "mill-vertfeed",
        "Mill vertical feed",
        "speed, default unspecified by current docs",
        "Sets plunge feed for isolation moves.",
        "Controls vertical feed into the board for milling. Keep conservative for small V-bits "
        "and fragile end mills.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "mill-infeed": _entry(
        "mill-infeed",
        "Mill infeed",
        "length, default unspecified by current docs",
        "Limits depth per milling pass.",
        "Forces multiple depth passes if the full `zwork` depth is larger. Useful for reducing "
        "load on small tools.",
        (SOURCE_COMMON, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "mill-speed": _entry(
        "mill-speed",
        "Mill speed",
        "RPM, default unspecified by current docs",
        "Sets spindle speed for isolation routing.",
        "Emits spindle speed for milling output. Match this to tool, material, and machine.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "mill-feed-direction": _entry(
        "mill-feed-direction",
        "Mill feed direction",
        "enum `any|climb|conventional`, default `any`",
        "Changes path direction preference and can affect optimization.",
        "Choose climb or conventional when burr direction or cut quality matters. The app "
        "requires `tsp-2opt` off for fixed feed direction.",
        (SOURCE_MILLING, SOURCE_DETAIL_HELP),
    ),
    "invert-gerbers": _entry(
        "invert-gerbers",
        "Invert Gerbers",
        "bool, default `false`",
        "Inverts milling polarity.",
        "Invert front/back polarity so milling happens inside shapes rather than outside them. "
        "Inspect preview and generated output carefully when enabled.",
        (SOURCE_MILLING, SOURCE_DETAIL_HELP),
    ),
    "draw-gerber-lines": _entry(
        "draw-gerber-lines",
        "Draw Gerber lines",
        "bool, default `false`",
        "Changes how Gerber line objects become toolpaths.",
        "Treat line objects as lines instead of filled shapes. Useful for silk plotting, "
        "scratching, pen plotting, and engraving-like work.",
        (SOURCE_MILLING, SOURCE_DETAIL_HELP),
    ),
    "preserve-thermal-reliefs": _entry(
        "preserve-thermal-reliefs",
        "Thermal reliefs",
        "bool, default `true`",
        "Affects milling geometry, mainly with `voronoi`.",
        "Try to keep thermal-relief intent instead of clearing it away during region routing.",
        (SOURCE_MILLING, SOURCE_DETAIL_HELP),
    ),
    "front-output": _entry(
        "front-output",
        "Front output",
        "path, default `front.ngc`",
        "None; controls output filename.",
        "Filename for front-layer NC output.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "back-output": _entry(
        "back-output",
        "Back output",
        "path, default `back.ngc`",
        "None; controls output filename.",
        "Filename for back-layer NC output.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "milldrill-diameter": _entry(
        "milldrill-diameter",
        "Milldrill diameter",
        "length, default unspecified by current docs",
        "Controls milldrilling geometry.",
        "Diameter of the end mill used to mill holes instead of drilling them. Use with "
        "`min-milldrill-hole-diameter` for modern threshold-based workflows.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "min-milldrill-hole-diameter": _entry(
        "min-milldrill-hole-diameter",
        "Min milldrill hole",
        "length, default `inf`",
        "Selects holes for milldrilling.",
        "Holes at or above this threshold are milldrilled; smaller holes remain regular drill "
        "operations. This implies a milldrill workflow.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "zdrill": _entry(
        "zdrill",
        "Drill Z",
        "length, default unspecified by current docs",
        "Sets drilling depth.",
        "Target drill depth. Ensure it clears the full board and sacrificial layer as needed.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "zmilldrill": _entry(
        "zmilldrill",
        "Milldrill Z",
        "length, default unspecified by current docs",
        "Sets milldrilling depth.",
        "Depth for holes milled with an end mill. If omitted, docs imply common use follows the "
        "drilling depth workflow.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "drill-feed": _entry(
        "drill-feed",
        "Drill feed",
        "speed, default unspecified by current docs",
        "Sets drill plunge feed.",
        "Feed rate for drilling cycles or explicit drilling moves.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "drill-speed": _entry(
        "drill-speed",
        "Drill speed",
        "RPM, default unspecified by current docs",
        "Sets drill spindle speed.",
        "Spindle speed for drilling output.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "drill-side": _entry(
        "drill-side",
        "Drill side",
        "enum `auto|front|back`, default `auto`",
        "Controls drilling coordinate side.",
        "Choose which side coordinate system to use for drilling. Prefer this over deprecated "
        "`drill-front` examples from older docs.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "drills-available": _entry(
        "drills-available",
        "Drills available",
        "size list with optional tolerances, default none",
        "Changes tool selection and tool changes.",
        "Quantize requested drill sizes to a real available-tool inventory. This reduces "
        "pointless tool changes and can simplify manual drilling.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "onedrill": _entry(
        "onedrill",
        "One drill",
        "bool, default `false`",
        "Changes drilling tool selection.",
        "Use one drill size only. Practical for pilot holes or simplified manual workflows.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "nog91-1": _entry(
        "nog91-1",
        "No G91.1",
        "bool, default `false`",
        "Suppresses `G91.1` in drill headers.",
        "Useful only if the controller dislikes explicit incremental arc-center mode.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "nog81": _entry(
        "nog81",
        "No G81",
        "bool, default `false`",
        "Replaces canned `G81` drill cycles with explicit `G0`/`G1` moves.",
        "High-value compatibility switch for GRBL-like controllers and other firmware that does "
        "not support canned drilling cycles.",
        (SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "nom6": _entry(
        "nom6",
        "No M6",
        "bool, default `false`",
        "Suppresses `M6` tool-change calls.",
        "Helpful where tool changes are manual, unsupported, or handled outside the program.",
        (SOURCE_MAN, SOURCE_DRILLING, SOURCE_DETAIL_HELP),
    ),
    "drill-output": _entry(
        "drill-output",
        "Drill output",
        "path, default `drill.ngc`",
        "None; controls output filename.",
        "Filename for drilling NC output.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "milldrill-output": _entry(
        "milldrill-output",
        "Milldrill output",
        "path, default `milldrill.ngc`",
        "None; controls output filename.",
        "Filename for milldrilling NC output.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "fill-outline": _entry(
        "fill-outline",
        "Fill outline",
        "bool, default `true`",
        "Affects outline geometry.",
        "Treat the outline layer as a closed line chain. The wiki says this assumes the contour "
        "is closed.",
        (SOURCE_OUTLINE, SOURCE_DETAIL_HELP),
    ),
    "cutter-diameter": _entry(
        "cutter-diameter",
        "Cutter diameter",
        "length, default unspecified by current docs",
        "Controls outline offset/geometry.",
        "Diameter of the tool used for outline cutting.",
        (SOURCE_OUTLINE, SOURCE_DETAIL_HELP),
    ),
    "zcut": _entry(
        "zcut",
        "Cut Z",
        "length, default unspecified by current docs",
        "Sets full outline cut depth.",
        "Full cut depth for board separation. Pair with `cut-infeed` to avoid overloading the "
        "tool in one pass.",
        (SOURCE_OUTLINE, SOURCE_DETAIL_HELP),
    ),
    "cut-feed": _entry(
        "cut-feed",
        "Cut feed",
        "speed, default unspecified by current docs",
        "Sets horizontal outline cutting feed.",
        "Feed rate while cutting the board outline laterally.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "cut-vertfeed": _entry(
        "cut-vertfeed",
        "Cut vertical feed",
        "speed, default unspecified by current docs",
        "Sets outline plunge feed.",
        "Vertical feed for outline cutting. Keep conservative for FR-4 and small cutters.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "cut-speed": _entry(
        "cut-speed",
        "Cut speed",
        "RPM, default unspecified by current docs",
        "Sets outline spindle speed.",
        "Spindle speed for outline/cutout output.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "cut-infeed": _entry(
        "cut-infeed",
        "Cut infeed",
        "length, default unspecified by current docs",
        "Limits outline depth per pass.",
        "Maximum depth per cutout pass. Smaller values reduce load and tool risk, especially in "
        "FR-4.",
        (SOURCE_COMMON, SOURCE_OUTLINE, SOURCE_DETAIL_HELP),
    ),
    "cut-side": _entry(
        "cut-side",
        "Cut side",
        "enum `auto|front|back`, default `auto`",
        "Controls outline coordinate side.",
        "Choose which board side coordinate system to use for cutout. Prefer this over "
        "deprecated `cut-front` examples from older docs.",
        (SOURCE_OUTLINE, SOURCE_DETAIL_HELP),
    ),
    "bridges": _entry(
        "bridges",
        "Bridges",
        "length, default `0`",
        "Creates holding tabs in outline paths.",
        "Width of each holding tab. Bridges intentionally leave material uncut so the PCB stays "
        "attached to stock during the final outline pass.",
        (SOURCE_OUTLINE, SOURCE_DETAIL_HELP),
    ),
    "bridgesnum": _entry(
        "bridgesnum",
        "Bridge count",
        "integer, default `2`",
        "Controls number of holding tabs.",
        "Number of holding tabs generated around the outline.",
        (SOURCE_OUTLINE, SOURCE_DETAIL_HELP),
    ),
    "zbridges": _entry(
        "zbridges",
        "Bridge Z",
        "length, default uses `zsafe` if unspecified",
        "Sets shallower bridge depth.",
        "Bridge cutting depth. It must be shallower than `zcut` to leave material. Historical "
        "bug reports exist for older builds, so inspect generated cutout code.",
        (SOURCE_OUTLINE, "issue #26", SOURCE_DETAIL_HELP),
    ),
    "outline-output": _entry(
        "outline-output",
        "Outline output",
        "path, default `outline.ngc`",
        "None; controls output filename.",
        "Filename for outline/cutout NC output.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "optimise": _entry(
        "optimise",
        "Optimise",
        "tolerance/length, default `2.54e-06m` in current docs",
        "Changes geometric simplification and output path fidelity.",
        "Modern spelling is `optimise`; old docs may show `optimize`. Larger values can shorten "
        "files and smooth geometry at the cost of fidelity.",
        (SOURCE_OPTIMIZATION, SOURCE_MAN, SOURCE_OBSOLETE_MANUAL, SOURCE_DETAIL_HELP),
    ),
    "eulerian-paths": _entry(
        "eulerian-paths",
        "Eulerian paths",
        "bool, default unspecified by current docs",
        "Changes path ordering to reduce lifts/rapids.",
        "Try Eulerian traversal where possible so the tool avoids milling the same path twice.",
        (SOURCE_OPTIMIZATION, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "vectorial": _entry(
        "vectorial",
        "Vectorial",
        "bool, default `true`",
        "Selects vector engine behavior.",
        "Effectively legacy because vectorial mode is the modern default path, but it remains in "
        "the option surface.",
        (SOURCE_OPTIMIZATION, SOURCE_DETAIL_HELP),
    ),
    "tsp-2opt": _entry(
        "tsp-2opt",
        "TSP 2OPT",
        "bool-like optimizer toggle, default unspecified by current docs",
        "Changes routing/travel ordering.",
        "Apply a 2-opt improvement step. More CPU can produce better ordering. Disable when "
        "using fixed `mill-feed-direction` in this UI.",
        (SOURCE_OPTIMIZATION, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "path-finding-limit": _entry(
        "path-finding-limit",
        "Path finding limit",
        "integer/limit, default unspecified by current docs",
        "Limits optimizer search effort.",
        "Lower values generate faster but can produce worse routes. Higher values can improve "
        "routes at the cost of planning time.",
        (SOURCE_MAN, SOURCE_OPTIMIZATION, SOURCE_DETAIL_HELP),
    ),
    "g0-vertical-speed": _entry(
        "g0-vertical-speed",
        "G0 vertical speed",
        "speed model parameter, default unspecified by current docs",
        "Affects internal planner cost, not emitted `G0` feed words.",
        "Planner estimate of vertical rapid speed. It changes path choice rather than machine "
        "rapid speed commands.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "g0-horizontal-speed": _entry(
        "g0-horizontal-speed",
        "G0 horizontal speed",
        "speed model parameter, default unspecified by current docs",
        "Affects internal planner cost, not emitted `G0` feed words.",
        "Planner estimate of horizontal rapid speed. It changes path choice rather than machine "
        "rapid speed commands.",
        (SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "backtrack": _entry(
        "backtrack",
        "Backtrack",
        "bool or optimizer control, default unspecified by current docs",
        "Changes routing/retraction strategy.",
        "Allow reuse or backtracking across already-cleared routes instead of retracting. This "
        "can reduce lifts on some jobs.",
        (SOURCE_MAN, SOURCE_OPTIMIZATION, SOURCE_DETAIL_HELP),
    ),
    "al-front": _entry(
        "al-front",
        "Autolevel front",
        "bool, default `false`",
        "Enables front-output probing/autolevelling sequence.",
        "Enable autoleveller for front milling output. Requires controller-specific probing "
        "settings.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "al-back": _entry(
        "al-back",
        "Autolevel back",
        "bool, default `false`",
        "Enables back-output probing/autolevelling sequence.",
        "Enable autoleveller for back milling output. Requires controller-specific probing "
        "settings.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "software": _entry(
        "software",
        "Software",
        "enum `linuxcnc|mach3|mach4|custom`, default unspecified by current docs",
        "Selects autolevelling probe dialect.",
        "Choose the target controller dialect. In `custom` mode, `al-probecode`, `al-probevar`, "
        "and `al-setzzero` define the probe command, result variable, and zeroing command.",
        (SOURCE_MAN, SOURCE_OBSOLETE_MANUAL, SOURCE_DETAIL_HELP),
    ),
    "al-x": _entry(
        "al-x",
        "Probe X",
        "length, default unspecified by current docs",
        "Controls autolevelling probe grid.",
        "Maximum X spacing between probe points. Smaller spacing improves Z fitting and "
        "increases probing time.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_DETAIL_HELP),
    ),
    "al-y": _entry(
        "al-y",
        "Probe Y",
        "length, default unspecified by current docs",
        "Controls autolevelling probe grid.",
        "Maximum Y spacing between probe points. Smaller spacing improves Z fitting and "
        "increases probing time.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_DETAIL_HELP),
    ),
    "al-probefeed": _entry(
        "al-probefeed",
        "Probe feed",
        "speed, default unspecified by current docs",
        "Sets autolevelling probe descent feed.",
        "Probe descent feed. Keep conservative to avoid probe or tool damage.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "al-probe-on": _entry(
        "al-probe-on",
        "Probe on",
        "string, default attach-message plus `M0` sequence",
        "Inserts raw probe preparation commands.",
        "Commands to run before probing. Docs note `@` as newline separator in string form.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_DETAIL_HELP),
    ),
    "al-probe-off": _entry(
        "al-probe-off",
        "Probe off",
        "string, default detach-message plus `M0` sequence",
        "Inserts raw probe cleanup commands.",
        "Commands to run after probing. Docs note `@` as newline separator in string form.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_DETAIL_HELP),
    ),
    "al-probecode": _entry(
        "al-probecode",
        "Probe code",
        "string, default `G31`",
        "Sets custom probing command.",
        "Probe command in custom mode. Controllers commonly need `G31`, `G38.2`, or another "
        "dialect-specific probing command.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "al-probevar": _entry(
        "al-probevar",
        "Probe variable",
        "integer, default `2002`",
        "Sets custom probe-result variable.",
        "Probe-result variable in custom autolevelling mode.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "al-setzzero": _entry(
        "al-setzzero",
        "Set Z zero",
        "string, default `G92 Z0`",
        "Sets custom Z-zero command after probing.",
        "Command used to set the current Z to zero after probing in custom mode.",
        (SOURCE_OBSOLETE_MANUAL, SOURCE_MAN, SOURCE_DETAIL_HELP),
    ),
    "x-offset": _entry(
        "x-offset",
        "X offset",
        "length, default `0`",
        "Applies global X translation.",
        "Global X offset for source artwork in preview and generation. Loaded NC preview files "
        "stay in their already-generated coordinates.",
        (SOURCE_ALIGNMENT, SOURCE_DETAIL_HELP),
    ),
    "y-offset": _entry(
        "y-offset",
        "Y offset",
        "length, default `0`",
        "Applies global Y translation.",
        "Global Y offset for source artwork in preview and generation. Loaded NC preview files "
        "stay in their already-generated coordinates.",
        (SOURCE_ALIGNMENT, SOURCE_DETAIL_HELP),
    ),
    "zero-start": _entry(
        "zero-start",
        "Zero start",
        "bool, default `false`",
        "Normalizes project coordinates near origin.",
        "Move the project into the positive quadrant near origin. Convenient, but easy to forget "
        "when aligning separate runs; it can contribute to front/back or drill/mill mismatch if "
        "used inconsistently.",
        (SOURCE_ALIGNMENT, "CNCZone discussion", SOURCE_DETAIL_HELP),
    ),
    "mirror-axis": _entry(
        "mirror-axis",
        "Mirror X axis",
        "length, default `0`",
        "Sets the two-sided mirror line.",
        "Mirror line for two-sided alignment, conceptually `x = axis` unless `mirror-yaxis` "
        "changes the dimension.",
        (SOURCE_ALIGNMENT, SOURCE_DETAIL_HELP),
    ),
    "mirror-yaxis": _entry(
        "mirror-yaxis",
        "Mirror Y axis",
        "bool/flag-like, default unspecified by current docs",
        "Changes mirror dimension.",
        "Flips the back side along Y instead of X. This also affects preview: back-side NC "
        "toolpaths are flipped vertically instead of horizontally, including when the Back "
        "preview side is selected.",
        (SOURCE_MAN, SOURCE_ALIGNMENT, SOURCE_DETAIL_HELP),
    ),
}
