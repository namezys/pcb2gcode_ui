from io import BytesIO
from pathlib import Path

from PIL import Image

from pcb2gcode_ui.gcode_preview import (
    GcodeInstrument,
    GcodeMovementKind,
    GcodePoint,
    GcodeSegment,
    GcodeSource,
    GcodeTrace,
)
from pcb2gcode_ui.preview import (
    DEFAULT_PREVIEW_DPMM,
    Bounds,
    DrillHit,
    DrillLayer,
    GerberPreviewRenderer,
    PreviewLayerKind,
    PreviewOptions,
    PreviewSide,
    RenderedLayer,
    TransformSettings,
    _apply_alpha,
    _compose_preview,
    _layer_color,
    _parse_drill_file,
    _tint_layer_image,
    _transform_point,
    _transformed_bounds,
)


def test_default_preview_resolution_is_high_quality():
    assert DEFAULT_PREVIEW_DPMM == 100
    assert PreviewOptions().dpmm == 100


def test_render_preview_uses_pygerber_api_for_example_board():
    values = {
        "front": "pcb2gcode/extras/example_board/example_board-F.Cu.gbr",
        "outline": "pcb2gcode/extras/example_board/example_board-Edge.Cuts.gbr",
        "metric": "true",
        "zero-start": "true",
        "x-offset": "1",
        "y-offset": "2",
        "tile-x": "2",
        "tile-y": "1",
    }

    result = GerberPreviewRenderer().render(
        values,
        Path.cwd(),
        PreviewOptions(show_drill=False, dpmm=3),
    )

    assert result.ok
    assert result.layer_count == 2
    image = Image.open(BytesIO(result.png))
    assert image.width > image.height


def test_render_preview_can_show_front_and_back():
    values = {
        "front": "pcb2gcode/extras/example_board/example_board-F.Cu.gbr",
        "back": "pcb2gcode/extras/example_board/example_board-B.Cu.gbr",
        "metric": "true",
    }

    result = GerberPreviewRenderer().render(
        values,
        Path.cwd(),
        PreviewOptions(show_front=True, show_back=True, show_drill=False, show_cutoff=False),
    )

    assert result.ok
    assert result.layer_count == 2
    assert _layer_color(PreviewLayerKind.FRONT) != _layer_color(PreviewLayerKind.BACK)


def test_render_preview_size_stays_stable_when_gerber_layers_are_hidden():
    values = {
        "front": "pcb2gcode/extras/example_board/example_board-F.Cu.gbr",
        "back": "pcb2gcode/extras/example_board/example_board-B.Cu.gbr",
        "metric": "true",
    }
    renderer = GerberPreviewRenderer()
    visible_result = renderer.render(
        values,
        Path.cwd(),
        PreviewOptions(show_front=True, show_back=True, show_drill=False, show_cutoff=False),
    )
    hidden_result = renderer.render(
        values,
        Path.cwd(),
        PreviewOptions(show_front=True, show_back=False, show_drill=False, show_cutoff=False),
    )

    visible_image = Image.open(BytesIO(visible_result.png))
    hidden_image = Image.open(BytesIO(hidden_result.png))

    assert hidden_image.size == visible_image.size
    assert hidden_result.layer_count == 1


def test_compose_preview_places_layers_in_shared_coordinate_system():
    front_color = _layer_color(PreviewLayerKind.FRONT)
    back_color = _layer_color(PreviewLayerKind.BACK)
    front_layer = RenderedLayer(
        image=Image.new("RGBA", (10, 10), (*front_color, 255)),
        kind=PreviewLayerKind.FRONT,
        bounds=Bounds(0, 0, 10, 10),
    )
    back_layer = RenderedLayer(
        image=Image.new("RGBA", (10, 10), (*back_color, 255)),
        kind=PreviewLayerKind.BACK,
        bounds=Bounds(20, 0, 30, 10),
    )
    settings = TransformSettings(
        metric=True,
        zero_start=False,
        mirror_yaxis=False,
        x_offset_mm=0,
        y_offset_mm=0,
        tile_x=1,
        tile_y=1,
        board_bounds=Bounds(0, 0, 30, 10),
    )

    image = _compose_preview(
        [front_layer, back_layer],
        None,
        Bounds(0, 0, 30, 10),
        settings,
        PreviewOptions(show_drill=False, show_cutoff=False, dpmm=1, layer_alpha=100),
    )

    assert image.getpixel((5, 5))[:3] == front_color
    assert image.getpixel((25, 5))[:3] == back_color


def test_compose_preview_front_side_paints_front_over_back():
    front_color = _layer_color(PreviewLayerKind.FRONT)
    back_color = _layer_color(PreviewLayerKind.BACK)
    front_layer = RenderedLayer(
        image=Image.new("RGBA", (1, 1), (*front_color, 255)),
        kind=PreviewLayerKind.FRONT,
        bounds=Bounds(0, 0, 1, 1),
    )
    back_layer = RenderedLayer(
        image=Image.new("RGBA", (1, 1), (*back_color, 255)),
        kind=PreviewLayerKind.BACK,
        bounds=Bounds(0, 0, 1, 1),
    )
    settings = _preview_settings(Bounds(0, 0, 1, 1))

    image = _compose_preview(
        [front_layer, back_layer],
        None,
        Bounds(0, 0, 1, 1),
        settings,
        PreviewOptions(show_drill=False, show_cutoff=False, dpmm=1, layer_alpha=100),
    )

    assert image.getpixel((0, 0))[:3] == front_color


def test_compose_preview_back_side_paints_back_over_front():
    front_color = _layer_color(PreviewLayerKind.FRONT)
    back_color = _layer_color(PreviewLayerKind.BACK)
    front_layer = RenderedLayer(
        image=Image.new("RGBA", (1, 1), (*front_color, 255)),
        kind=PreviewLayerKind.FRONT,
        bounds=Bounds(0, 0, 1, 1),
    )
    back_layer = RenderedLayer(
        image=Image.new("RGBA", (1, 1), (*back_color, 255)),
        kind=PreviewLayerKind.BACK,
        bounds=Bounds(0, 0, 1, 1),
    )
    settings = _preview_settings(Bounds(0, 0, 1, 1))

    image = _compose_preview(
        [front_layer, back_layer],
        None,
        Bounds(0, 0, 1, 1),
        settings,
        PreviewOptions(
            side=PreviewSide.BACK,
            show_drill=False,
            show_cutoff=False,
            dpmm=1,
            layer_alpha=100,
        ),
    )

    assert image.getpixel((0, 0))[:3] == back_color


def test_compose_preview_paints_drill_cutoff_and_aux_after_copper():
    aux_color = _layer_color(PreviewLayerKind.AUX)
    front_layer = RenderedLayer(
        image=Image.new("RGBA", (5, 5), (*_layer_color(PreviewLayerKind.FRONT), 255)),
        kind=PreviewLayerKind.FRONT,
        bounds=Bounds(0, 0, 5, 5),
    )
    cutoff_layer = RenderedLayer(
        image=Image.new("RGBA", (5, 5), (*_layer_color(PreviewLayerKind.CUTOFF), 255)),
        kind=PreviewLayerKind.CUTOFF,
        bounds=Bounds(0, 0, 5, 5),
    )
    aux_layer = RenderedLayer(
        image=Image.new("RGBA", (5, 5), (*aux_color, 255)),
        kind=PreviewLayerKind.AUX,
        bounds=Bounds(0, 0, 5, 5),
    )
    drill_layer = DrillLayer([DrillHit(2, 2, 1)], [])
    settings = _preview_settings(Bounds(0, 0, 5, 5))

    image = _compose_preview(
        [aux_layer, cutoff_layer, front_layer],
        drill_layer,
        Bounds(0, 0, 5, 5),
        settings,
        PreviewOptions(dpmm=1, layer_alpha=100),
    )

    assert image.getpixel((2, 3))[:3] == aux_color


def test_compose_preview_front_side_alpha_affects_only_front_and_drill():
    front_color = _layer_color(PreviewLayerKind.FRONT)
    back_color = _layer_color(PreviewLayerKind.BACK)
    front_layer = RenderedLayer(
        image=Image.new("RGBA", (1, 1), (*front_color, 255)),
        kind=PreviewLayerKind.FRONT,
        bounds=Bounds(0, 0, 1, 1),
    )
    back_layer = RenderedLayer(
        image=Image.new("RGBA", (1, 1), (*back_color, 255)),
        kind=PreviewLayerKind.BACK,
        bounds=Bounds(0, 0, 1, 1),
    )
    settings = _preview_settings(Bounds(0, 0, 1, 1))

    image = _compose_preview(
        [front_layer, back_layer],
        None,
        Bounds(0, 0, 1, 1),
        settings,
        PreviewOptions(show_drill=False, show_cutoff=False, dpmm=1, layer_alpha=50),
    )

    expected = Image.new("RGBA", (1, 1), (*back_color, 255))
    expected.alpha_composite(_apply_alpha(Image.new("RGBA", (1, 1), (*front_color, 255)), 50))
    assert image.getpixel((0, 0)) == expected.getpixel((0, 0))


def test_compose_preview_back_side_alpha_affects_only_back_and_drill():
    front_color = _layer_color(PreviewLayerKind.FRONT)
    back_color = _layer_color(PreviewLayerKind.BACK)
    front_layer = RenderedLayer(
        image=Image.new("RGBA", (1, 1), (*front_color, 255)),
        kind=PreviewLayerKind.FRONT,
        bounds=Bounds(0, 0, 1, 1),
    )
    back_layer = RenderedLayer(
        image=Image.new("RGBA", (1, 1), (*back_color, 255)),
        kind=PreviewLayerKind.BACK,
        bounds=Bounds(0, 0, 1, 1),
    )
    settings = _preview_settings(Bounds(0, 0, 1, 1))

    image = _compose_preview(
        [front_layer, back_layer],
        None,
        Bounds(0, 0, 1, 1),
        settings,
        PreviewOptions(
            side=PreviewSide.BACK,
            show_drill=False,
            show_cutoff=False,
            dpmm=1,
            layer_alpha=50,
        ),
    )

    expected = Image.new("RGBA", (1, 1), (*front_color, 255))
    expected.alpha_composite(_apply_alpha(Image.new("RGBA", (1, 1), (*back_color, 255)), 50))
    assert image.getpixel((0, 0)) == expected.getpixel((0, 0))


def test_compose_preview_back_side_mirrors_all_layers_horizontally():
    front_color = _layer_color(PreviewLayerKind.FRONT)
    layer_image = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    layer_image.putpixel((0, 0), (*front_color, 255))
    front_layer = RenderedLayer(
        image=layer_image,
        kind=PreviewLayerKind.FRONT,
        bounds=Bounds(0, 0, 2, 1),
    )
    settings = _preview_settings(Bounds(0, 0, 2, 1))

    image = _compose_preview(
        [front_layer],
        None,
        Bounds(0, 0, 2, 1),
        settings,
        PreviewOptions(
            side=PreviewSide.BACK,
            show_drill=False,
            show_cutoff=False,
            dpmm=1,
            layer_alpha=100,
        ),
    )

    assert image.getpixel((1, 0))[:3] == front_color


def test_compose_preview_back_side_mirrors_drills_horizontally():
    drill_color = (87, 178, 255)
    drill_layer = DrillLayer([DrillHit(2, 5, 1)], [])
    settings = _preview_settings(Bounds(0, 0, 10, 10))

    image = _compose_preview(
        [],
        drill_layer,
        Bounds(0, 0, 10, 10),
        settings,
        PreviewOptions(
            side=PreviewSide.BACK,
            show_front=False,
            show_back=False,
            show_cutoff=False,
            dpmm=1,
            layer_alpha=100,
        ),
    )

    assert image.getpixel((8, 5))[:3] == drill_color


def test_compose_preview_alpha_affects_drill():
    drill_layer = DrillLayer([DrillHit(5, 5, 1)], [])
    settings = _preview_settings(Bounds(0, 0, 10, 10))

    image = _compose_preview(
        [],
        drill_layer,
        Bounds(0, 0, 10, 10),
        settings,
        PreviewOptions(
            show_front=False,
            show_back=False,
            show_cutoff=False,
            dpmm=1,
            layer_alpha=50,
        ),
    )

    assert image.getpixel((5, 5)) == (87, 178, 255, 128)


def test_compose_preview_draws_gcode_cut_over_retract():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 1, 1),
                GcodePoint(10, 1, 1),
                GcodeMovementKind.RETRACT,
                "1",
                "front",
                1,
            ),
            GcodeSegment(
                GcodePoint(0, 5, -0.1),
                GcodePoint(10, 5, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "front",
                2,
            ),
        ],
        [],
    )
    settings = _preview_settings(Bounds(0, 0, 10, 10))

    image = _compose_preview(
        [],
        None,
        Bounds(0, 0, 10, 10),
        settings,
        PreviewOptions(
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=1,
        ),
        trace,
    )

    assert image.getpixel((5, 5))[3] > image.getpixel((5, 9))[3]
    assert image.getpixel((5, 5))[:3] != (32, 35, 38)


def test_compose_preview_colors_gcode_by_tool_path():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 2, -0.1),
                GcodePoint(10, 2, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "front",
                1,
                "front-1",
            ),
            GcodeSegment(
                GcodePoint(0, 8, -0.1),
                GcodePoint(10, 8, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "front",
                2,
                "front-2",
            ),
            GcodeSegment(
                GcodePoint(0, 5, -0.1),
                GcodePoint(10, 5, -0.1),
                GcodeMovementKind.CUT,
                "2",
                "front",
                3,
                "front-3",
            ),
        ],
        [],
        [
            GcodeInstrument("front-1", "1", "front", 1, 1),
            GcodeInstrument("front-2", "1", "front", 2, 2),
            GcodeInstrument("front-3", "2", "front", 3, 3),
        ],
    )
    settings = _preview_settings(Bounds(0, 0, 10, 10))

    image = _compose_preview(
        [],
        None,
        Bounds(0, 0, 10, 10),
        settings,
        PreviewOptions(show_front=False, show_drill=False, show_cutoff=False, show_gcode=True),
        trace,
    )

    assert image.getpixel((500, 800))[:3] == image.getpixel((500, 200))[:3]
    assert image.getpixel((500, 500))[:3] != image.getpixel((500, 200))[:3]


def test_compose_preview_draws_retract_as_dots():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 5, 1),
                GcodePoint(10, 5, 1),
                GcodeMovementKind.RETRACT,
                "1",
                "front",
                1,
                "front-1",
            ),
        ],
        [],
        [GcodeInstrument("front-1", "1", "front", 1, 1)],
    )
    settings = _preview_settings(Bounds(0, 0, 10, 10))

    image = _compose_preview(
        [],
        None,
        Bounds(0, 0, 10, 10),
        settings,
        PreviewOptions(
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=10,
        ),
        trace,
    )

    assert image.getpixel((0, 50))[:3] != (32, 35, 38)
    assert image.getpixel((2, 50))[:3] != (32, 35, 38)
    assert image.getpixel((5, 50))[:3] != (32, 35, 38)


def test_compose_preview_draws_front_gcode_axis():
    trace = GcodeTrace([], [], [], [GcodeSource("front", "front.nc")])
    settings = _preview_settings(Bounds(0, 0, 4, 4))

    image = _compose_preview(
        [],
        None,
        Bounds(-1, -1, 5, 5),
        settings,
        PreviewOptions(
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=10,
        ),
        trace,
    )

    assert image.getpixel((30, 50))[:3] == (210, 216, 222)
    assert image.getpixel((10, 30))[:3] == (210, 216, 222)


def test_compose_preview_draws_back_gcode_axis_mirrored_from_origin():
    trace = GcodeTrace([], [], [], [GcodeSource("back", "back.nc")])
    settings = _preview_settings(Bounds(0, 0, 4, 4))

    image = _compose_preview(
        [],
        None,
        Bounds(-5, -1, 1, 5),
        settings,
        PreviewOptions(
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=10,
        ),
        trace,
    )

    assert image.getpixel((30, 50))[:3] == (210, 216, 222)


def test_compose_preview_draws_back_gcode_axis_flipped_y_when_enabled():
    trace = GcodeTrace([], [], [], [GcodeSource("back", "back.nc")])
    settings = _preview_settings(Bounds(0, 0, 4, 4), mirror_yaxis=True)

    image = _compose_preview(
        [],
        None,
        Bounds(-1, -5, 5, 1),
        settings,
        PreviewOptions(
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=10,
        ),
        trace,
    )

    assert image.getpixel((30, 10))[:3] == (210, 216, 222)
    assert image.getpixel((10, 30))[:3] == (210, 216, 222)


def test_compose_preview_mirrors_back_gcode_axis_on_back_side():
    trace = GcodeTrace([], [], [], [GcodeSource("back", "back.nc")])
    settings = _preview_settings(Bounds(0, 0, 4, 4))

    image = _compose_preview(
        [],
        None,
        Bounds(-5, -1, 1, 5),
        settings,
        PreviewOptions(
            side=PreviewSide.BACK,
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=10,
        ),
        trace,
    )

    assert image.getpixel((30, 50))[:3] == (210, 216, 222)


def test_compose_preview_scales_gcode_axis_from_largest_trace_size():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 1, -0.1),
                GcodePoint(100, 1, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "front",
                1,
            ),
        ],
        [],
        [],
        [GcodeSource("front", "front.nc")],
    )
    settings = _preview_settings(Bounds(0, 0, 100, 4))

    image = _compose_preview(
        [],
        None,
        Bounds(-1, -1, 101, 14.5),
        settings,
        PreviewOptions(
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=1,
        ),
        trace,
    )

    assert image.getpixel((1, 2))[:3] == (210, 216, 222)


def test_compose_preview_draws_gcode_paths_over_axis():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 0, -0.1),
                GcodePoint(4, 0, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "front",
                1,
            ),
        ],
        [],
        [],
        [GcodeSource("front", "front.nc")],
    )
    settings = _preview_settings(Bounds(0, 0, 4, 4))

    image = _compose_preview(
        [],
        None,
        Bounds(-1, -1, 5, 5),
        settings,
        PreviewOptions(
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=10,
        ),
        trace,
    )

    assert image.getpixel((30, 50))[:3] == (255, 214, 78)


def test_compose_preview_back_side_mirrors_gcode_horizontally():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 5, -0.1),
                GcodePoint(0, 5, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "front",
                1,
            ),
            GcodeSegment(
                GcodePoint(0, 5, -0.1),
                GcodePoint(2, 5, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "front",
                2,
            ),
        ],
        [],
    )
    settings = _preview_settings(Bounds(0, 0, 10, 10))

    image = _compose_preview(
        [],
        None,
        Bounds(0, 0, 10, 10),
        settings,
        PreviewOptions(
            side=PreviewSide.BACK,
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=1,
        ),
        trace,
    )

    assert image.getpixel((9, 5))[:3] != (32, 35, 38)


def test_compose_preview_mirrors_back_gcode_on_front_side():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 5, -0.1),
                GcodePoint(2, 5, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "back",
                1,
            ),
        ],
        [],
    )
    settings = _preview_settings(Bounds(-2, 0, 10, 10))

    image = _compose_preview(
        [],
        None,
        Bounds(-2, 0, 10, 10),
        settings,
        PreviewOptions(
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=1,
        ),
        trace,
    )

    assert image.getpixel((1, 5))[:3] != (32, 35, 38)


def test_compose_preview_flips_back_gcode_y_axis_when_enabled():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(2, 3, -0.1),
                GcodePoint(4, 3, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "back",
                1,
            ),
        ],
        [],
    )
    settings = _preview_settings(Bounds(0, 0, 10, 10), mirror_yaxis=True)

    image = _compose_preview(
        [],
        None,
        Bounds(0, -10, 10, 10),
        settings,
        PreviewOptions(
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=1,
        ),
        trace,
    )

    assert image.getpixel((3, 13))[:3] != (32, 35, 38)
    assert image.getpixel((7, 7))[:3] == (32, 35, 38)


def test_compose_preview_back_side_mirrors_back_gcode_with_layout():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 5, -0.1),
                GcodePoint(2, 5, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "back",
                1,
            ),
        ],
        [],
    )
    settings = _preview_settings(Bounds(-2, 0, 10, 10))

    image = _compose_preview(
        [],
        None,
        Bounds(-2, 0, 10, 10),
        settings,
        PreviewOptions(
            side=PreviewSide.BACK,
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=1,
        ),
        trace,
    )

    assert image.getpixel((10, 5))[:3] != (32, 35, 38)


def test_compose_preview_back_side_uses_mirror_yaxis_back_gcode_layout():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(2, 3, -0.1),
                GcodePoint(4, 3, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "back",
                1,
            ),
        ],
        [],
    )
    settings = _preview_settings(Bounds(0, 0, 10, 10), mirror_yaxis=True)

    image = _compose_preview(
        [],
        None,
        Bounds(0, -10, 10, 10),
        settings,
        PreviewOptions(
            side=PreviewSide.BACK,
            show_front=False,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            dpmm=1,
        ),
        trace,
    )

    assert image.getpixel((7, 13))[:3] != (32, 35, 38)
    assert image.getpixel((3, 13))[:3] == (32, 35, 38)


def test_transformed_bounds_include_origin_mirrored_back_gcode():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 5, -0.1),
                GcodePoint(2, 5, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "back",
                1,
            ),
        ],
        [],
    )
    settings = _preview_settings(Bounds(0, 0, 2, 10))

    bounds = _transformed_bounds([], None, settings, trace)

    assert bounds.min_x == -6
    assert bounds.max_x == 2


def test_transformed_bounds_include_mirror_yaxis_back_gcode():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 5, -0.1),
                GcodePoint(2, 5, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "back",
                1,
            ),
        ],
        [],
    )
    settings = _preview_settings(Bounds(0, 0, 2, 10), mirror_yaxis=True)

    bounds = _transformed_bounds([], None, settings, trace)

    assert bounds.min_y == -7
    assert bounds.max_y == 2


def test_transformed_bounds_include_empty_gcode_source_axis():
    trace = GcodeTrace([], [], [], [GcodeSource("front", "front.nc")])
    settings = _preview_settings(Bounds(0, 0, 4, 4))

    bounds = _transformed_bounds([], None, settings, trace)

    assert bounds.min_x == -2
    assert bounds.min_y == -2
    assert bounds.max_x == 6
    assert bounds.max_y == 6


def test_transformed_bounds_scale_gcode_axis_from_largest_trace_size():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 0, -0.1),
                GcodePoint(100, 0, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "front",
                1,
            ),
        ],
        [],
    )
    settings = _preview_settings(Bounds(0, 0, 100, 1))

    bounds = _transformed_bounds([], None, settings, trace)

    assert bounds.max_y == 14.5


def test_render_preview_size_stays_stable_when_gcode_is_hidden():
    trace = GcodeTrace(
        [
            GcodeSegment(
                GcodePoint(0, 0, -0.1),
                GcodePoint(100, 0, -0.1),
                GcodeMovementKind.CUT,
                "1",
                "front",
                1,
            ),
        ],
        [],
        [],
        [GcodeSource("front", "front.nc")],
    )
    values = {"front": "pcb2gcode/extras/example_board/example_board-F.Cu.gbr", "metric": "true"}
    renderer = GerberPreviewRenderer()
    visible_result = renderer.render(
        values,
        Path.cwd(),
        PreviewOptions(
            show_front=True,
            show_drill=False,
            show_cutoff=False,
            show_gcode=True,
            gcode_trace=trace,
            dpmm=1,
        ),
    )
    hidden_result = renderer.render(
        values,
        Path.cwd(),
        PreviewOptions(
            show_front=True,
            show_drill=False,
            show_cutoff=False,
            show_gcode=False,
            gcode_trace=trace,
            dpmm=1,
        ),
    )

    visible_image = Image.open(BytesIO(visible_result.png))
    hidden_image = Image.open(BytesIO(hidden_result.png))

    assert hidden_image.size == visible_image.size
    assert hidden_result.layer_count == 1


def test_compose_preview_does_not_mirror_back_layer():
    back_color = _layer_color(PreviewLayerKind.BACK)
    layer_image = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    layer_image.putpixel((0, 0), (*back_color, 255))
    back_layer = RenderedLayer(
        image=layer_image,
        kind=PreviewLayerKind.BACK,
        bounds=Bounds(0, 0, 2, 1),
    )
    settings = TransformSettings(
        metric=True,
        zero_start=False,
        mirror_yaxis=False,
        x_offset_mm=0,
        y_offset_mm=0,
        tile_x=1,
        tile_y=1,
        board_bounds=Bounds(0, 0, 2, 1),
    )

    image = _compose_preview(
        [back_layer],
        None,
        Bounds(0, 0, 2, 1),
        settings,
        PreviewOptions(show_drill=False, show_cutoff=False, dpmm=1, layer_alpha=100),
    )

    assert image.getpixel((0, 0))[:3] == back_color


def test_render_preview_can_show_single_aux_layer():
    values = {"metric": "true"}

    result = GerberPreviewRenderer().render(
        values,
        Path.cwd(),
        PreviewOptions(
            show_front=False,
            show_back=False,
            show_drill=False,
            show_cutoff=False,
            show_aux=True,
            aux_layer=Path("pcb2gcode/extras/example_board/example_board-F.Cu.gbr"),
            dpmm=3,
        ),
    )

    assert result.ok
    assert result.layer_count == 1


def test_render_preview_uses_cutoff_fallback_for_eagle_profile(tmp_path: Path):
    profile_path = tmp_path / "profile.gbr"
    profile_path.write_text(
        "\n".join(
            [
                "G04 EAGLE Gerber RS-274X export*",
                "G75*",
                "%MOMM*%",
                "%FSLAX34Y34*%",
                "%LPD*%",
                "%IN*%",
                "%IPPOS*%",
                "%ADD10C,0.254000*%",
                "D10*",
                "X49530Y25400D02*",
                "X190300Y25400D01*",
                "X190300Y314200D01*",
                "X49530Y314200D01*",
                "X49530Y25400D01*",
                "M02*",
            ]
        ),
        encoding="utf-8",
    )

    result = GerberPreviewRenderer().render(
        {"outline": str(profile_path), "metric": "true"},
        tmp_path,
        PreviewOptions(show_front=False, show_drill=False, dpmm=4),
    )

    assert result.ok
    assert result.layer_count == 1
    assert result.warnings == []
    image = Image.open(BytesIO(result.png))
    assert image.width > 50
    assert image.height > 100


def test_apply_alpha_changes_layer_alpha_channel():
    image = Image.new("RGBA", (1, 1), (10, 20, 30, 200))

    result = _apply_alpha(image, 50)

    assert result.getpixel((0, 0)) == (10, 20, 30, 100)


def test_tint_layer_image_preserves_alpha_and_changes_color():
    image = Image.new("RGBA", (1, 1), (255, 255, 255, 180))

    result = _tint_layer_image(image, (1, 2, 3))

    assert result.getpixel((0, 0)) == (1, 2, 3, 180)


def test_parse_drill_file_reads_decimal_metric_hits(tmp_path: Path):
    drill_path = tmp_path / "board.drl"
    drill_path.write_text(
        "\n".join(
            [
                "M48",
                "METRIC",
                "T01C0.8",
                "%",
                "T01",
                "X1.5Y2.5",
            ]
        ),
        encoding="utf-8",
    )

    layer = _parse_drill_file(drill_path)

    assert not layer.warnings
    assert len(layer.hits) == 1
    assert layer.hits[0].x_mm == 1.5
    assert layer.hits[0].y_mm == 2.5
    assert layer.hits[0].diameter_mm == 0.8


def test_parse_drill_file_reads_metric_implied_decimal_hits(tmp_path: Path):
    drill_path = tmp_path / "board.xln"
    drill_path.write_text(
        "\n".join(
            [
                "M48",
                "METRIC,TZ,000.000",
                "T1C1.016",
                "%",
                "M71",
                "T1",
                "X7620Y6350",
            ]
        ),
        encoding="utf-8",
    )

    layer = _parse_drill_file(drill_path)

    assert not layer.warnings
    assert len(layer.hits) == 1
    assert layer.hits[0].x_mm == 7.62
    assert layer.hits[0].y_mm == 6.35
    assert layer.hits[0].diameter_mm == 1.016


def test_render_preview_with_implied_decimal_drill_file(tmp_path: Path):
    drill_path = tmp_path / "board.xln"
    drill_path.write_text(
        "\n".join(
            [
                "M48",
                "METRIC,TZ,000.000",
                "T1C1.016",
                "%",
                "M71",
                "T1",
                "X7620Y6350",
                "X10160Y6350",
            ]
        ),
        encoding="utf-8",
    )

    result = GerberPreviewRenderer().render(
        {"drill": str(drill_path), "metric": "true"},
        tmp_path,
        PreviewOptions(show_front=False, show_cutoff=False),
    )

    assert result.ok
    image = Image.open(BytesIO(result.png))
    assert image.width < 700
    assert image.height < 500


def test_render_preview_rejects_oversized_canvas(monkeypatch, tmp_path: Path):
    drill_path = tmp_path / "board.xln"
    drill_path.write_text(
        "\n".join(
            [
                "M48",
                "METRIC",
                "T1C1.000",
                "%",
                "T1",
                "X99999999Y99999999",
            ]
        ),
        encoding="utf-8",
    )
    front_path = tmp_path / "front.gbr"
    front_path.write_text("", encoding="utf-8")
    layer = RenderedLayer(
        image=Image.new("RGBA", (1, 1), (*_layer_color(PreviewLayerKind.FRONT), 255)),
        kind=PreviewLayerKind.FRONT,
        bounds=Bounds(0, 0, 1, 1),
    )

    monkeypatch.setattr(GerberPreviewRenderer, "_render_gerber_layers", lambda *args: [layer])

    result = GerberPreviewRenderer().render(
        {"front": str(front_path), "drill": str(drill_path), "metric": "true"},
        tmp_path,
        PreviewOptions(show_cutoff=False),
    )

    assert not result.ok
    assert any("Preview canvas is too large" in warning for warning in result.warnings)


def test_transform_point_applies_zero_start_offsets():
    settings = TransformSettings(
        metric=True,
        zero_start=True,
        mirror_yaxis=False,
        x_offset_mm=1,
        y_offset_mm=2,
        tile_x=1,
        tile_y=1,
        board_bounds=Bounds(5, 10, 25, 30),
    )

    assert _transform_point(6, 12, settings) == (2, 4)


def _preview_settings(bounds: Bounds, mirror_yaxis: bool = False) -> TransformSettings:
    return TransformSettings(
        metric=True,
        zero_start=False,
        mirror_yaxis=mirror_yaxis,
        x_offset_mm=0,
        y_offset_mm=0,
        tile_x=1,
        tile_y=1,
        board_bounds=bounds,
    )
