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
