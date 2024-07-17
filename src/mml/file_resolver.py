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

import ctypes
import gc
import logging
import multiprocessing
import threading
import time

from mml.artifact import Artifact
from mml.resolver_process import resolver_process

# To prevent overloading and smooth queue handling
LOOP_DELAY = 0.25

# Progress log interval
STATS_INTERVAL = 1.0


def sizeof_fmt(num, suffix="B") -> str:
    """Format number of bytes to human readable form
    By Fred Cirera
    <https://web.archive.org/web/20111010015624/http://blogmag.net/blog/read/38/Print_human_readable_file_size>
    """
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


class FileResolver:
    def __init__(
        self,
        workers_num: int,
        logging_queue: multiprocessing.Queue,
        clear_on_finish: bool = True,
        clear_on_error: bool = True,
    ):
        """Initializes FileResolver instance
        This class process and downloads files from the queue

        Args:
            workers_num (int): number of processes to resolve files data
            logging_queue (multiprocessing.Queue): queue for worker_configurer()
            clear_on_finish (bool, optional): True to call clear() on finish. Defaults to True
            clear_on_error (bool, optional): True to call clear() in case of error. Defaults to True
        """
        self._workers_num = workers_num
        self._logging_queue = logging_queue
        self._clear_on_finish = clear_on_finish
        self._clear_on_error = clear_on_error

        self._queue = multiprocessing.Queue(-1)
        self._bytes_total = 0

        self._stop_flag = multiprocessing.Value(ctypes.c_bool, False)
        self._error_flag = multiprocessing.Value(ctypes.c_bool, False)
        self._bytes_processed = multiprocessing.Value(ctypes.c_uint64, 0)

        # Start background loop
        self._workers = []
        self._checker_loop_running = True
        self._finished = True
        self._stats_timer = time.time()
        logging.debug("Starting _checker_loop()")
        self._checker_thread = threading.Thread(target=self._checker_loop, daemon=True)
        self._checker_thread.start()

    @property
    def finished(self) -> bool:
        """
        Returns:
            bool: True if nothing to process
        """
        if not self._queue.empty():
            return False
        return self._finished

    def add_artifact(self, artifact_: Artifact) -> None:
        """Adds artifact to the queue and number of total bytes
        Args:
            artifact_ (Artifact): artifact to process
        """
        logging.debug(f"Adding artifact {artifact_} to the queue. Size: {artifact_.size}")
        self._bytes_total += artifact_.size
        self._queue.put(artifact_)

        logging.debug("_checker_loop() stopped")

    @property
    def error(self) -> bool:
        """
        Returns:
            bool: True in case of error occurred while processing files
        """
        with self._error_flag.get_lock():
            error_flag_ = self._error_flag.value
        return error_flag_

    def clear_error(self) -> None:
        """Clears error flag"""
        with self._error_flag.get_lock():
            self._error_flag.value = False

    @property
    def bytes_total(self) -> int:
        """
        Returns:
            int: number of bytes to process and download (from add_artifact())
        """
        return self._bytes_total

    @property
    def bytes_processed(self) -> int:
        """
        Returns:
            int: number of bytes already processed (approx.)
        """
        with self._bytes_processed.get_lock():
            bytes_processed_ = self._bytes_processed.value
        return bytes_processed_

    def reset_bytes(self) -> None:
        """Resets bytes_total and bytes_processed"""
        self._bytes_total = 0
        with self._bytes_processed.get_lock():
            self._bytes_processed.value = 0

    def get_progress(self) -> float:
        """
        Returns:
            float: processing progress in [0-1] range
        """
        with self._bytes_processed.get_lock():
            bytes_processed_ = self._bytes_processed.value
        if self._bytes_total != 0 and bytes_processed_ <= self._bytes_total:
            return bytes_processed_ / self._bytes_total
        return 0.0 if self._bytes_total == 0 else 1.0

    def clear(self) -> None:
        """Clears queue, bytes_total, bytes_processed and calls garbage collector
        NOTE: Doesn't clear error flag! You must clear it manually
        """
        while not self._queue.empty():
            self._queue.get()

        self.reset_bytes()
        gc.collect()

    def stop(self, stop_background_thread: bool = False) -> None:
        """Stops all processes, _checker_loop() and clear the queue
        Doesn't clear error flag, so you can detect if error occurs

        Args:
            stop_background_thread (bool, optional): True to stop _checker_loop(). Defaults to False
        """
        logging.info("Stopping file resolver")

        # Request stop
        with self._stop_flag.get_lock():
            if not self._stop_flag.value:
                self._stop_flag.value = True

        # Wait for processes to finish gracefully
        if len(self._workers) != 0:
            logging.debug("Waiting for workers to finish")
        while len(self._workers) != 0:
            for worker in self._workers:
                if worker is None or not worker.is_alive():
                    logging.debug(f"Worker {worker} is dead now. Removing it")
                    del self._workers[self._workers.index(worker)]
            time.sleep(LOOP_DELAY)

        # Stop thread and wait for it to stop
        if stop_background_thread:
            self._checker_loop_running = False
            if self._checker_thread.is_alive():
                logging.debug("Waiting for _checker_thread")
                self._checker_thread.join()

        # Clear everything
        self.clear()

        logging.info("File resolver stopped")

    def _stats_cli(self) -> None:
        """Prints resolver stats each STATS_INTERVAL"""
        if time.time() - self._stats_timer >= STATS_INTERVAL:
            self._stats_timer = time.time()
            progress = self.get_progress() * 100.0
            logging.info(
                f"Processed {sizeof_fmt(self.bytes_processed)} / {sizeof_fmt(self.bytes_total)} ({progress:.2f}%)"
            )

    def _checker_loop(self) -> None:
        """Checks for data in queue and starts / stops the workers"""
        logging.debug("_checker_loop() started")
        cleared = True
        while self._checker_loop_running:
            # Check workers and remove exited ones
            for worker in self._workers:
                if worker is None or not worker.is_alive():
                    logging.debug(f"Worker {worker} is dead now. Removing it")
                    del self._workers[self._workers.index(worker)]

            # Check for errors
            with self._error_flag.get_lock():
                error_flag_ = self._error_flag.value

            # Stop all workers in case of error or if nothing to process
            if error_flag_ or (self._queue.empty() and len(self._workers) != 0):
                with self._stop_flag.get_lock():
                    if not self._stop_flag.value:
                        logging.debug("Stopping workers")
                        self._stop_flag.value = True

            # Start workers if we have data to process and no errors
            if not error_flag_ and not self._queue.empty() and len(self._workers) == 0:
                cleared = False
                self._finished = False
                with self._stop_flag.get_lock():
                    if self._stop_flag.value:
                        self._stop_flag.value = False
                for i in range(self._workers_num):
                    logging.debug(f"Starting worker {i + 1}")
                    worker = multiprocessing.Process(
                        target=resolver_process,
                        args=(
                            i + 1,
                            self._queue,
                            self._stop_flag,
                            self._error_flag,
                            self._bytes_processed,
                            self._logging_queue,
                        ),
                    )
                    worker.start()
                    self._workers.append(worker)
                    time.sleep(0.1)

            # Resolving considered finished only after all process are finished
            if len(self._workers) == 0 and self._queue.empty():
                self._finished = True

            # Clear queue, error flag and stats
            if (
                not cleared
                and len(self._workers) == 0
                and (self._clear_on_error and error_flag_ or self._clear_on_finish and not error_flag_)
            ):
                self.clear()
                cleared = True

            # Print progress
            if len(self._workers) != 0 and self._bytes_total != 0:
                self._stats_cli()

            # Sleep a bit to prevent overloading
            time.sleep(LOOP_DELAY)
