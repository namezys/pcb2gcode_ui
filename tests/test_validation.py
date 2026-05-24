from pcb2gcode_ui.validation import validate_values


def test_validate_values_requires_milling_fields_when_front_is_selected():
    messages = validate_values({"front": "front.gbr", "zsafe": "5", "zchange": "10"})

    assert {message.key for message in messages} == {
        "zwork",
        "mill-diameters",
        "mill-feed",
        "mill-speed",
    }


def test_validate_values_rejects_fixed_feed_direction_with_tsp():
    messages = validate_values(
        {
            "zsafe": "5",
            "zchange": "10",
            "mill-feed-direction": "climb",
            "tsp-2opt": "true",
        }
    )

    assert [message.key for message in messages] == ["mill-feed-direction"]


def test_validate_values_requires_align_drill_diameter_when_enabled_with_drill():
    messages = validate_values(
        {
            "drill": "drill.drl",
            "outline": "outline.gbr",
            "zsafe": "5",
            "zchange": "10",
            "zdrill": "-1",
            "drill-feed": "100",
            "drill-speed": "1000",
            "zcut": "-1",
            "cutter-diameter": "1",
            "cut-feed": "100",
            "cut-speed": "1000",
            "cut-infeed": "0.5",
            "pre-align-drills": "true",
        }
    )

    assert [message.key for message in messages] == ["pre-align-drill-diameter"]


def test_validate_values_rejects_non_positive_align_drill_diameter():
    messages = validate_values(
        {
            "drill": "drill.drl",
            "outline": "outline.gbr",
            "zsafe": "5",
            "zchange": "10",
            "zdrill": "-1",
            "drill-feed": "100",
            "drill-speed": "1000",
            "zcut": "-1",
            "cutter-diameter": "1",
            "cut-feed": "100",
            "cut-speed": "1000",
            "cut-infeed": "0.5",
            "pre-align-drills": "true",
            "pre-align-drill-diameter": "0",
        }
    )

    assert [message.text for message in messages] == ["Value must be positive."]
