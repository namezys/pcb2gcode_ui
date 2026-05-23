from pcb2gcode_ui.help_content import GENERAL_HELP, OPTION_HELP_BY_KEY, option_help_markdown
from pcb2gcode_ui.options import OPTION_SPECS


def test_every_ui_option_has_help_entry():
    option_keys = {spec.key for spec in OPTION_SPECS}

    assert option_keys <= set(OPTION_HELP_BY_KEY)


def test_general_help_describes_main_workflow():
    assert "millproject" in GENERAL_HELP.markdown
    assert "Preview" in GENERAL_HELP.markdown
    assert "Validate" in GENERAL_HELP.markdown
    assert "Generate NC" in GENERAL_HELP.markdown


def test_high_risk_help_entries_include_gotchas():
    checks = {
        "mill-diameters": ("unsafe", "0"),
        "offset": ("isolation-width", "mill-diameters"),
        "zsafe": ("safety-critical", "clamps"),
        "nog81": ("GRBL", "G0"),
        "zero-start": ("mismatch", "separate runs"),
        "mirror-yaxis": ("underexplained", "verify"),
        "bridges": ("holding tab", "attached"),
        "software": ("custom", "probe"),
    }

    for key, expected_fragments in checks.items():
        markdown = option_help_markdown(OPTION_HELP_BY_KEY[key]).lower()
        assert all(fragment.lower() in markdown for fragment in expected_fragments)
