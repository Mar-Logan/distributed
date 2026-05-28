import logging


def setup_logger():

    logger = logging.getLogger("DistResClient")

    logger.setLevel(logging.DEBUG)

    if not logger.handlers:

        console_handler = logging.StreamHandler()

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%H:%M:%S"
        )

        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger