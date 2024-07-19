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

import hashlib
import logging
import os
import queue
import re
import subprocess
import sys
import time
from enum import IntEnum
from functools import reduce
from threading import Thread
from typing import Dict, List

from mml._version import LAUNCHER_VERSION
from mml.deps_builder import DepsBuilder
from mml.file_resolver import FileResolver
from mml.jdk_check_install import classpath_separator
from mml.profile_parser import ProfileParser

# For -Dminecraft.launcher.brand argument
LAUNCHER_NAME = "minecraft-launcher"

# Main class to launch if not found in profile
MAIN_CLASS_DEFAULT = "net.minecraft.launchwrapper.Launch"

# To replace <XMLLayout /> and <LegacyXMLLayout />
LOG_CONFIG_LAYOUT = '<PatternLayout pattern="[%t/%level]: %msg{nolookups}%n" />'

# How long to wait for minecraft process to stops by itself after MINECRAFT_STOPPING_LOG before killing it
MINECRAFT_STOPPING_LOG = "(\\[Render thread\\/INFO\\]\\: Stopping\\!|\\!\\[CDATA\\[Stopping\\!\\]\\])"
MINECRAFT_STOPPING_TIMEOUT = 3.0

ON_POSIX = "posix" in sys.builtin_module_names


class State(IntEnum):
    IDLE = 0
    PREPARING = 1
    JAVA = 2
    CLIENT = 3
    ASSETS = 4
    LIBRARIES = 5
    LOG_CONFIG = 6
    PROCESS_FILES = 7
    PRELAUNCH = 8
    MINECRAFT = 9
    ERROR = -1


class Launcher(Thread):
    def __init__(
        self,
        file_resolver_: FileResolver,
        profile_parser_: ProfileParser,
        version_id: str,
        env_variables: Dict or None = None,
        features: Dict or None = None,
        user_name: str or None = None,
        auth_uuid: str or None = None,
        auth_access_token: str or None = None,
        user_type: str or None = None,
        isolate_profile: bool = True,
        java_path: str or None = None,
        extra_jvm_args: List[str] or None = None,
        extra_game_args: List[str] or None = None,
    ) -> None:
        Thread.__init__(self)
        self._file_resolver = file_resolver_
        self._profile_parser = profile_parser_
        self._version_id = version_id
        self._env_variables = env_variables
        self._features = features
        self._user_name = user_name
        self._auth_uuid = auth_uuid
        self._auth_access_token = auth_access_token
        self._user_type = user_type
        self._isolate_profile = isolate_profile
        self._java_path = java_path
        self._extra_jvm_args = extra_jvm_args
        self._extra_game_args = extra_game_args

        if self._features is None:
            self._features = {}

        self._state = State.IDLE
        self._minecraft_process = None

    @property
    def state(self) -> State:
        """
        Returns:
            int: current state. See State class for available states
        """
        return self._state

    def run(self) -> None:
        if self._state != State.IDLE and self._state != State.ERROR:
            logging.error("Unable to launch. Already running?")
            return

        self._state = State.PREPARING

        # Parse versions if not parsed yet
        if not self._profile_parser.versions_info:
            self._profile_parser.parse_versions()

        try:
            # Get or download profile's JSON
            version_path = self._profile_parser.version_path_by_id(self._version_id, download=True)
            if not version_path:
                logging.error(f"Unable to load version {self._version_id}")
                self._state = State.ERROR
                return
            version_json = self._profile_parser.parse_version_json(version_path)
            if not version_json:
                logging.error(f"Unable to load version {self._version_id}")
                self._state = State.ERROR
                return

            # Use version's dir if we need to isolate profile
            cwd = (
                os.path.join(self._profile_parser.versions_dir, self._version_id)
                if self._isolate_profile
                else self._profile_parser.game_dir
            )

            logging.info("Preparing data")

            self._file_resolver.clear()

            # Create dependency builder instance
            deps_builder_ = DepsBuilder(
                self._file_resolver.add_artifact,
                self._profile_parser.game_dir,
                self._profile_parser.versions_dir,
                self._version_id,
                version_json,
            )

            # Download Java
            self._state = State.JAVA
            if not self._java_path or not os.path.exists(self._java_path):
                self._java_path = deps_builder_.get_java()
                if not self._java_path:
                    raise Exception("Unable to get Java")
                logging.debug("get_java() done")

            # Download client
            self._state = State.CLIENT
            client_jar = deps_builder_.get_client()
            if not client_jar:
                raise Exception("Unable to get client")
            logging.debug("get_client() done")

            # Resolve assets
            self._state = State.ASSETS
            asset_index = deps_builder_.get_assets()
            if not asset_index:
                raise Exception("Unable to get assets")
            logging.debug("get_assets() done")

            # Resolve libraries and natives
            self._state = State.LIBRARIES
            libs = deps_builder_.get_libraries()
            if libs is None:
                raise Exception("Unable to get libraries")
            logging.debug("get_libraries() done")

            self._state = State.LOG_CONFIG
            log_config_path, log_config_arg = deps_builder_.get_log_config()
            logging.debug("get_log_config() done")

            # Replace <LegacyXMLLayout /> to be able to read config from stdout without 3rd-party parser
            if log_config_path:
                logging.info(f"Modifying log config: {log_config_path}")
                with open(log_config_path, "r", encoding="utf-8") as log_config_io:
                    log_config = log_config_io.read()
                log_config = log_config.replace("<XMLLayout />", LOG_CONFIG_LAYOUT)
                log_config = log_config.replace("<LegacyXMLLayout />", LOG_CONFIG_LAYOUT)
                with open(log_config_path, "w+", encoding="utf-8") as log_config_io:
                    log_config_io.write(log_config)

            # Wait for everything to resolve
            self._state = State.PROCESS_FILES
            logging.info("Waiting for file resolver to finish")
            while not self._file_resolver.finished:
                time.sleep(0.1)

            # Check for error -> clear it and exit
            if self._file_resolver.error:
                self._file_resolver.clear_error()
                logging.error("File resolver finished with error")
                self._state = State.ERROR
                return

            logging.info("File resolver finished successfully")
            self._state = State.PRELAUNCH

            # Build classpath from client and all libraries
            classpath = [client_jar]
            for lib in libs:
                classpath.append(os.path.join(deps_builder_.libs_dir, lib))

            # Build environment variables
            env_variables_ = {
                "game_directory": cwd,
                "library_directory": deps_builder_.libs_dir,
                "natives_directory": os.path.join(self._profile_parser.versions_dir, deps_builder_.natives_dir),
                "classpath_separator": classpath_separator(),
                "classpath": classpath_separator().join(classpath),
                "game_assets": deps_builder_.assets_legacy_dir,
                "assets_root": deps_builder_.assets_dir,
                "assets_index_name": asset_index,
                "version_name": self._version_id,
                "version_type": version_json.get("type", "release"),
                "launcher_version": str(LAUNCHER_VERSION),
                "launcher_name": LAUNCHER_NAME,
                "auth_player_name": self._user_name,
                "auth_access_token": self._auth_access_token if self._auth_access_token else "0",
                "user_type": self._user_type if self._user_type else "mojang",
            }

            # Enable demo mode if no username provided
            if not self._user_name:
                self._features["is_demo_user"] = True

            # Username provided, but UUID not -> generate offline one
            elif not self._auth_uuid:
                auth_uuid = bytearray(hashlib.md5(f"OfflinePlayer:{self._user_name}".encode("utf-8")).digest())
                auth_uuid[6] = auth_uuid[6] & 0x0F | 0x30
                auth_uuid[8] = auth_uuid[8] & 0x3F | 0x80
                # self._auth_uuid = str(UUID(bytes=bytes(auth_uuid)))
                self._auth_uuid = auth_uuid.hex()

            # Set uuid
            if self._auth_uuid:
                env_variables_["auth_uuid"] = self._auth_uuid

            # Overwrite env variables with custom ones
            if self._env_variables:
                env_variables_.update(self._env_variables)

            # Add java args
            final_cmd = [self._java_path]
            final_cmd.extend(deps_builder_.get_arguments(False, self._features))
            if self._extra_jvm_args:
                final_cmd.extend(self._extra_jvm_args)

            # Log config
            if log_config_arg:
                final_cmd.append(log_config_arg)

            # Main class
            main_class = version_json.get("mainClass", MAIN_CLASS_DEFAULT)
            final_cmd.append(main_class)

            # Add game (minecraft) args
            final_cmd.extend(deps_builder_.get_arguments(True, self._features))
            if self._extra_game_args:
                final_cmd.extend(self._extra_game_args)

            # Replace env placeholders in arguments
            for i, argument in enumerate(final_cmd):
                # Search for placeholders
                try:
                    match_ = re.findall("\\$\\{[^\\$\\}\\{]+\\}", argument)
                except (AttributeError, IndexError):
                    continue

                # Remove duplicates
                unique_placeholders = reduce(lambda re, x: re + [x] if x not in re else re, match_, [])

                # Replace
                for placeholder in unique_placeholders:
                    env_variable_name = placeholder[2:-1]

                    # Try to get from env_variables or from os.environ
                    if env_variable_name in env_variables_:
                        env_value = env_variables_.get(env_variable_name)
                    else:
                        env_value = os.environ.get(env_variable_name)
                    if not env_value:
                        env_value = ""
                        logging.warning(f"No environment variable {env_variable_name}")

                    # Replace
                    final_cmd[i] = final_cmd[i].replace(placeholder, env_value)

            # Clone environ and replace
            environ_copy = os.environ.copy()
            for var_name, var_value in env_variables_.items():
                environ_copy[var_name] = var_value
            logging.debug(f"Environment: {environ_copy}")

            # Log final command
            logging.info(f"Full command: {' '.join(final_cmd)}")

            # Finally, start minecraft's process
            self._state = State.MINECRAFT
            self._minecraft_process = subprocess.Popen(
                final_cmd,
                bufsize=1,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                close_fds=ON_POSIX,
                shell=False,
                cwd=cwd,
                env=environ_copy,
            )

            stdout_queue = queue.Queue()
            stdout_thread = Thread(target=self._enqueue_output, args=(stdout_queue,), daemon=True)
            stdout_thread.start()

            stopping_timer = 0
            level = logging.info

            # Capture logs
            while self._minecraft_process.poll() is None:
                # Read logs from STOUT (non-blocking way)
                try:
                    minecraft_stdout = stdout_queue.get(block=False)
                except queue.Empty:
                    time.sleep(0.1)
                    self._check_kill(stopping_timer)
                    continue

                log_line = minecraft_stdout.decode("utf-8", errors="replace").strip()

                # Try to guess log level
                if "INFO" in log_line:
                    level = logging.info
                if "WARN" in log_line:
                    level = logging.warning
                elif "ERROR" in log_line:
                    level = logging.error

                # Redirect log
                level(f"[Minecraft] {log_line}")

                # Start timer if there is MINECRAFT_STOPPING_LOG message
                if re.search(MINECRAFT_STOPPING_LOG, log_line):
                    logging.info(f"Stopping message found! Minecraft must exit in {MINECRAFT_STOPPING_TIMEOUT}s")
                    stopping_timer = time.time()

            # Minecraft closed
            logging.info("Minecraft process stopped")
            self._state = State.IDLE

        except Exception as e:
            self._state = State.ERROR
            logging.error(f"Error launching minecraft: {e}", exc_info=e)

    def stop(self) -> None:
        """Stops any downloads (file resolvers), minecraft and waits for the launcher thread to stop"""
        if self._state == State.IDLE or self._state == State.ERROR:
            logging.debug("Nothing to stop")
            return

        # Stop file resolver
        if not self._file_resolver.finished:
            self._file_resolver.stop()

        # Kill minecraft
        logging.warning("Stop requested")
        if self._minecraft_process:
            try:
                logging.warning("Trying to kill minecraft process")
                self._minecraft_process.kill()
            except Exception as e:
                logging.warning(f"Unable to kill minecraft process: {e}")
                logging.debug("Error details", exc_info=e)

        # Wait for thread
        if self.is_alive():
            try:
                logging.info("Waiting for launcher thread to stop")
                self.join()
            except Exception as e:
                logging.warning(f"Unable to join launcher thread: {e}")
                logging.debug("Error details", exc_info=e)

        logging.info("Launcher thread stopped")

    def _enqueue_output(self, queue_: queue.Queue) -> None:
        """Handler for reading lines from minecraft's STDOUT and putting them into queue_"""
        logging.debug("_enqueue_output() started")
        for line in iter(self._minecraft_process.stdout.readline, b""):
            queue_.put(line)
        self._minecraft_process.stdout.close()
        logging.debug("_enqueue_output() finished")

    def _check_kill(self, stopping_timer: float) -> None:
        """Checks if there is more then MINECRAFT_STOPPING_TIMEOUT after MINECRAFT_STOPPING_LOG and kills minecraft

        Args:
            stopping_timer (float): time of MINECRAFT_STOPPING_LOG
        """
        if stopping_timer != 0 and time.time() - stopping_timer > MINECRAFT_STOPPING_TIMEOUT:
            logging.warning("Minecraft process was unable to finish by itself. Killing it")
            self._minecraft_process.kill()
            time.sleep(1)
