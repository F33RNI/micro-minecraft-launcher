"""
This file is part of the micro-minecraft-launcher distribution.
See <https://github.com/F33RNI/micro-minecraft-launcher> for more info.

Copyright (C) 2024 Fern Lane

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.
If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import logging.handlers
import multiprocessing
import queue
import time
from ctypes import c_bool

# Logging formatter
FORMATTER_FMT = "[%(asctime)s] [%(levelname)-.1s] %(message)s"
FORMATTER_FMT_SUFFIX = "[%(asctime)s] [%(levelname)-.1s] [{suffix}] %(message)s"
FORMATTER_DATEFMT = "%Y-%m-%d %H:%M:%S"


def worker_configurer(queue_: multiprocessing.Queue, suffix: str | None = None):
    """Call this method in your process

    Args:
        queue (multiprocessing.Queue): logging queue
        suffix (str | None, optional): suffix for formatter for current process. Defaults to None
    """
    # Remove all current handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    # Setup queue handler
    queue_handler = logging.handlers.QueueHandler(queue_)
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(logging.DEBUG)

    # Configure formatter
    formatter = logging.Formatter(
        FORMATTER_FMT_SUFFIX.format(suffix=suffix) if suffix else FORMATTER_FMT, datefmt=FORMATTER_DATEFMT
    )
    queue_handler.setFormatter(formatter)

    # Log test message
    logging.debug(f"Logging setup is complete for process with PID: {multiprocessing.current_process().pid}")


class LoggingHandler:
    def __init__(self, verbose: bool = False):
        """Initializer LoggingHandler instance

        Args:
            verbose (bool, optional): True for DEBUG level, False for INFO. Defaults to False
        """
        self._verbose = verbose

        self._queue = multiprocessing.Queue(-1)
        self._flush_request = multiprocessing.Value(c_bool, False)

    @property
    def queue_(self) -> multiprocessing.Queue:
        """
        Returns:
            multiprocessing.Queue: logging queue
        """
        return self._queue

    def flush(self) -> None:
        """Requests handlers flush and waits until flushed"""
        with self._flush_request.get_lock():
            self._flush_request.value = True
        while True:
            with self._flush_request.get_lock():
                flush_request = self._flush_request.value
            if not flush_request:
                break
            time.sleep(0.01)

    def configure_and_start_listener(self):
        """Initializes logging and starts listening. Send None to queue to stop it"""
        # This import must be here
        # pylint: disable-next=import-outside-toplevel
        import sys

        # Setup logging into console
        console_handler = logging.StreamHandler(sys.stdout)

        # Add all handlers and setup level
        level = logging.DEBUG if self._verbose else logging.INFO
        root_logger = logging.getLogger()
        root_logger.addHandler(console_handler)
        root_logger.setLevel(level)

        # Start queue listener
        while True:
            try:
                # Handle flush request
                with self._flush_request.get_lock():
                    if self._flush_request.value:
                        logging.debug("Flushing logging handlers")
                        for handler in root_logger.handlers:
                            handler.flush()
                    self._flush_request.value = False

                # Get logging record (non-blocking)
                try:
                    record = self._queue.get(block=False)
                except queue.Empty:
                    time.sleep(0.1)
                    continue

                # Send None to exit
                if record is None:
                    break

                # Skip empty messages and lower levels
                if record.message is None or record.levelno < level:
                    continue

                # Handle current logging record
                logger = logging.getLogger(record.name)
                logger.handle(record)

            # Ignore Ctrl+C (call queue.put(None) to stop this listener)
            except (SystemExit, KeyboardInterrupt):
                pass

            # Error! WHY???
            except Exception:
                # pylint: disable=import-outside-toplevel
                import traceback

                # pylint: enable=import-outside-toplevel

                print("Logging error: ", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
