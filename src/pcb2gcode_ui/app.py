import logging

LOGGER = logging.getLogger(__name__)
LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"
NOISY_LOGGERS = ("flet_transport",)


def main():
    configure_logging()
    LOGGER.debug("Starting pcb2gcode UI")

    from pcb2gcode_ui.ui import run_app

    run_app()


def configure_logging():
    logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
    for logger_name in NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.INFO)
