import logging

from pcb2gcode_ui.app import configure_logging


def test_configure_logging_filters_flet_transport_debug_logs():
    logging.getLogger("flet_transport").setLevel(logging.DEBUG)

    configure_logging()

    assert logging.getLogger("flet_transport").level == logging.INFO
