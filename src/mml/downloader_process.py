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
import multiprocessing
import queue
import time

from mml.download_artifact import download_artifact
from mml.logging_handler import worker_configurer

# To prevent overloading but must be small to prevent waiting between data
LOOP_DELAY = 0.05


def downloader_process(
    id_: int,
    queue_: multiprocessing.Queue,
    stop_flag: multiprocessing.Value,
    error_flag: multiprocessing.Value,
    bytes_downloaded: multiprocessing.Value,
    logging_queue: multiprocessing.Queue,
) -> None:
    """Retrieves artifact instances from the queue and downloads them

    Args:
        if_ (int): worker id (1 - ...) for logging
        queue_ (multiprocessing.Queue): queue of artifact instances
        stop_flag (multiprocessing.Value): set tot True to stop the process
        error_flag (multiprocessing.Value): this will be set to True in case of error
        bytes_downloaded (multiprocessing.Value): will be incremented with size of artifact after downloading it
        logging_queue (multiprocessing.Queue): queue for worker_configurer()
    """
    # Setup logging for current process
    worker_configurer(logging_queue, suffix=f"D{id_:2}")

    # Process loop
    while True:
        # Non-blocking way to get data from the queue or exit by stop_flag
        while True:
            with stop_flag.get_lock():
                stop_flag_ = stop_flag.value
            if stop_flag_:
                logging.debug("downloader_process() finished")
                return

            try:
                data = queue_.get(block=False)
                if data:
                    break
            except queue.Empty:
                pass

            time.sleep(LOOP_DELAY)

        # This must not cause any errors!
        try:
            if not download_artifact(data):
                raise Exception("Unable to download artifact")

            # Increment by size of artifact
            with bytes_downloaded.get_lock():
                bytes_downloaded.value += data.size

        # Catch SIGTERM and CTRL+C
        except (SystemExit, KeyboardInterrupt):
            logging.warning("Interrupted")
            with error_flag.get_lock():
                error_flag.value = True
            return

        # Main loop error -> set error flag and exit
        except Exception as e_:
            with error_flag.get_lock():
                error_flag.value = True
            logging.error(e_)
            logging.debug("downloader_process() finished due to error or interrupt", exc_info=e_)
            return
