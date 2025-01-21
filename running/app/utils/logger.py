#  running/app/utils/logger.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
import logging
import os


# ------------------------------------------------ Function Definitions ------------------------------------------------
def setup_logging(log_directory="logs", log_file_name="app.log"):
    """
    Sets up logging to a given file in a given directory.
    """

    #  define the logger
    logger = logging.getLogger("app_logger")
    logger.setLevel(logging.DEBUG)

    #  define log file path
    log_file = os.path.join(log_directory, log_file_name)

    #  ensure log directory exists
    os.makedirs(log_directory, exist_ok=True)

    #  create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    #  create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    #  add handler to logger
    logger.addHandler(file_handler)

    return logger

# -------------------------------------------------- Main Code Execution -----------------------------------------------
if __name__ == "__main__":
    logger = setup_logging()
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")

