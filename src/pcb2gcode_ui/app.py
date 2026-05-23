import logging

LOGGER = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s")
    LOGGER.debug("Starting pcb2gcode UI")

    from pcb2gcode_ui.ui import run_app

    run_app()
