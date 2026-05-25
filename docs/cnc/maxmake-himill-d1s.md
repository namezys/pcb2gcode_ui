# MaxMake HiMill D1S

This page records CNC-specific notes for using `pcb2gcode-ui` output with the MaxMake HiMill D1S.
It is intentionally separate from the main manual so other CNC-specific details can be added later.

## Initial Version Warning

This manual and the app describe an initial version. A lot of bugs can exist.

The project was vibecoded, and code quality or correctness was not the primary concern during
development. You **must** double-check generated NC files, preview output, tool lists, controller
behavior, and machine setup before running a CNC job.

## Software Version

Use **MaxMakeLab 9.17** for this workflow.

Do not use **MaxMakeLab 9.16**. It does not work correctly for this output and can generate or
load invalid coordinates such as `Xnan Ynan`.

## Tool Change Behavior

HiMill D1S supports `M6`, so NC files should keep `M6` tool-change commands. Do not enable
`nom6` for this CNC.

HiMill D1S does not support separated `T*` tool-select commands. If `M6` is present in the NC
files, remove standalone tool-select commands by using the MaxMake profile or enabling
`post-remove-t=true`.

When the controller moves the head to the probe position on tool change, `pcb2gcode` can place a
`G00 Z...` command soon after the tool change. That is unsafe if the tool is still above the probe
position. Use the MaxMake profile or enable `post-origin-before-m3=true` so the post-processor
inserts:

```gcode
G00 X0.00000 Y0.00000
```

before spindle start after the tool change sequence.

## Required App Settings

Use the **MaxMake** profile when possible. It locks the post-processing options needed for this
machine:

- Remove `T*` tool-select commands.
- Move to `X0 Y0` before `M3`.

For two-sided boards:

- Enable alignment.
- Enable alignment drill pre-processing.
- Use M2 or M3 screws for the alignment holes.
- Use alignment drill depth around `4` or `5`.
- Set drilling and cutting to run from the back side.

## Two-sided PCB Flow

1. Enable alignment and alignment drill pre-processing.
2. Enable post-processing: remove `T*` and move to origin before `M3`.
3. Load the front NC file in MaxMakeLab.
4. Build the height map and apply it.
5. Remove the 3D probe.
6. Start the program. The CNC will ask for tool changes when needed.
7. Mill the front side.
8. Load the alignment drill NC file.
9. Drill the alignment holes.
10. Turn the board over.
11. Align the board using the drilled holes and M2 or M3 screws.
12. Load the back NC file.
13. Build the height map and apply it.
14. Remove the 3D probe.
15. Start the back program. The CNC will ask for tool changes when needed.
16. Load the drill NC file.
17. Perform drilling. The CNC will ask for each tool change.
18. Load the cutoff or outline NC file.
19. Cut out the PCB.

After the final cut, the two-sided PCB job is complete.

## Checks Before Running

- Confirm MaxMakeLab is version 9.17.
- Confirm NC files contain `M6` tool-change commands.
- Confirm separated `T*` commands were removed.
- Confirm origin moves were inserted before `M3`.
- Confirm alignment drill output is front-side only.
- Confirm drilling and cutoff are generated for the back side.
- Confirm `tools.md` matches the tools you expect to install.
