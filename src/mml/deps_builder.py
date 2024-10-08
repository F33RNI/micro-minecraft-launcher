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

import json
import logging
import os
from typing import Callable

from mml.artifact import Artifact
from mml.jdk_check_install import jdk_check_install
from mml.resolve_artifact import resolve_artifact
from mml.rules_check import os_name, rules_check

# Relative to game_dir
ASSETS_DIR = "assets"

# Relative to game_dir
ASSET_INDEXES_DIR = os.path.join(ASSETS_DIR, "indexes")

# Relative to game_dir
ASSET_OBJECTS_DIR = os.path.join(ASSETS_DIR, "objects")

# Relative to game_dir
ASSET_LEGACY_DIR = os.path.join(ASSETS_DIR, "virtual", "legacy")

# Path to download objects from asset index
ASSET_OBJECT_DOWNLOAD_URL = "https://resources.download.minecraft.net/{hash:.2}/{hash}"

# Relative to game_dir
LIBRARIES_DIR = "libraries"

# Relative to versions/version_id
NATIVES_DIR = "natives"

# Relative to game_dir
LOG_CONFIGS_DIR = os.path.join(ASSETS_DIR, "log_configs")

# Java arguments for old versions
JVM_ARGS_OLD = [
    "-Djava.library.path=${natives_directory}",
    "-cp",
    "${classpath}",
]


class DepsBuilder:
    def __init__(
        self,
        add_artifact: Callable[[Artifact], None],
        game_dir: str,
        version_dir: str,
        version_id: str,
        version_json: dict,
    ):
        self._add_artifact = add_artifact
        self._game_dir = game_dir
        self._version_dir = version_dir
        self._version_id = version_id
        self._version_json = version_json

    @property
    def natives_dir(self) -> str:
        """
        Returns:
            str: full path to native
        """
        return os.path.join(self._version_dir, self._version_id, NATIVES_DIR)

    @property
    def libs_dir(self) -> str:
        """
        Returns:
            str: full path to libraries dir
        """
        return os.path.join(self._game_dir, LIBRARIES_DIR)

    @property
    def assets_dir(self) -> str:
        """
        Returns:
            str: full path to assets dir
        """
        return os.path.join(self._game_dir, ASSETS_DIR)

    @property
    def assets_legacy_dir(self) -> str:
        """
        Returns:
            str: full path to assets/virtual/legacy dir
        """
        return os.path.join(self._game_dir, ASSET_LEGACY_DIR)

    def get_java(self) -> str | None:
        """Tries to download (if needed) correct version of Java for version

        Returns:
            str | None: path to java executable or None if case or error
        """
        return jdk_check_install(self._version_json.get("javaVersion", {}).get("majorVersion", 8))

    def get_client(self) -> str | None:
        """Tries to download (if needed) client (version.jar)

        Returns:
            str | None: path to client or None if case or error
        """
        client_path = os.path.join(self._version_dir, self._version_id, self._version_id + ".jar")
        logging.debug(f"Client path: {client_path}")

        # Check and try to download
        if "downloads" in self._version_json and "client" in self._version_json["downloads"]:
            if not resolve_artifact(
                Artifact(
                    self._version_json["downloads"]["client"],
                    parent_dir=os.path.join(self._version_dir, self._version_id),
                    target_file=os.path.join(self._version_id + ".jar"),
                )
            ):
                return None

        if os.path.exists(client_path):
            logging.debug(f"Client path: {client_path}")
            return client_path
        return None

    def get_assets(self) -> str | None:
        """Downloads all assets

        Returns:
            str | None: asset index if they're downloaded successfully or None in case of error
        """
        if "assets" not in self._version_json:
            logging.warning("No assets specified")
            return None

        assets_id = self._version_json["assets"]

        if "assetIndex" not in self._version_json or self._version_json["assetIndex"].get("id") != assets_id:
            logging.warning("Unable to download assets. Wrong assetIndex")
            return None

        # Download asset index
        asset_index_path = resolve_artifact(
            Artifact(
                self._version_json["assetIndex"],
                parent_dir=os.path.join(self._game_dir, ASSET_INDEXES_DIR),
                target_file=f"{assets_id}.json",
            )
        )
        if not asset_index_path:
            return None

        # Parse it
        with open(asset_index_path, "r", encoding="utf-8") as asset_index_io:
            asset_index = json.load(asset_index_io)

        # map_to_resources = asset_index.get("map_to_resources", False)
        legacy_dir = os.path.join(self._game_dir, ASSET_LEGACY_DIR)

        # Download all objects
        objects_root = os.path.join(self._game_dir, ASSET_OBJECTS_DIR)
        for object_name, object_data in asset_index.get("objects", {}).items():
            object_hash = object_data.get("hash")
            if not object_hash:
                continue

            # Copy to legacy dir
            # copy_to = None
            # if map_to_resources:
            copy_to = os.path.normpath(os.path.join(legacy_dir, object_name))

            # Build artifact and add it to the queue
            asset_artifact = Artifact(
                {
                    "url": ASSET_OBJECT_DOWNLOAD_URL.format(hash=object_hash),
                    "sha1": object_hash,
                    "size": object_data.get("size"),
                },
                parent_dir=objects_root,
                target_file=os.path.join(object_hash[:2], object_hash),
                copy_to=copy_to,
            )
            self._add_artifact(asset_artifact)

        # Seems Ok
        return assets_id

    def get_libraries(self) -> list[str] | None:
        """Build and downloads list of all libraries including native ones

        Returns:
            list[str] | None: ["path/to/lib/relative/to/libraries/dir", ...] or None in case of error
        """
        if "libraries" not in self._version_json:
            logging.warning("No libraries specified")
            return []

        libs_dir = os.path.join(self._game_dir, LIBRARIES_DIR)
        natives_dir = self.natives_dir
        os_name_ = os_name()

        libs = []
        for library in self._version_json["libraries"]:
            if "name" not in library:
                continue

            # Check rules (both new and old format)
            if ("rules" in library and not rules_check(library["rules"])) or (
                "clientreq" in library and library["clientreq"] == False
            ):
                logging.debug(f"Skipping library {library['name']}. Disallowed by rules")
                continue

            # Determine available classifiers
            classifiers_dict = library.get("downloads", {}).get("classifiers", library.get("classifiers"))

            # Determine main artifact
            artifact_dict = library.get("downloads", {}).get("artifact", library.get("artifact"))
            if artifact_dict is None and not classifiers_dict:
                artifact_dict = library

            # Add main artifact to the final list and download queue
            if artifact_dict:
                artifact_ = Artifact(artifact_dict, parent_dir=libs_dir)
                self._add_artifact(artifact_)
                libs.append(artifact_.path)
            else:
                logging.debug("Skipping main artifact. Only natives required?")

            # Add natives to the final list and download and unpack them
            if classifiers_dict and "natives" in library and os_name_ in library["natives"]:
                classifier_name = library["natives"][os_name_]
                if classifier_name in classifiers_dict:
                    # Add native artifact to the queue
                    native_artifact = Artifact(
                        classifiers_dict[classifier_name],
                        parent_dir=libs_dir,
                        unpack_into=natives_dir,
                        exclude_files=library.get("extract", {}).get("exclude", []),
                    )
                    libs.append(native_artifact.path)
                    self._add_artifact(native_artifact)

        return libs

    def get_log_config(self) -> tuple[str | None, str | None]:
        """Downloads log config if needed and extracts argument if exists

        Returns:
           tuple[str | None, str | None]: path to log config file, logging (JVM) argument
        """
        logging_client = self._version_json.get("logging", {}).get("client", {})
        if not logging_client or "argument" not in logging_client or "file" not in logging_client:
            return None, None

        logging_artifact = Artifact(
            logging_client["file"],
            parent_dir=os.path.join(self._game_dir, LOG_CONFIGS_DIR),
            target_file=logging_client["file"]["id"],
        )
        log_config_path = resolve_artifact(logging_artifact, verify_checksums=False)
        if not log_config_path:
            return None, None

        return log_config_path, logging_client["argument"].replace("${path}", log_config_path)

    def get_arguments(self, game: bool, features: dict | None) -> list[str]:
        """Parses game and jvm arguments

        Args:
            game (bool): True to parse game (or minecraftArguments)
            features (dict | None): see rules_check() docs

        Returns:
            list[str]: parsed arguments
        """
        args = self._version_json.get("arguments", {})

        # Game arguments
        if game:
            args = args.get("game", [])

            # Convert from old format
            if not args and "minecraftArguments" in self._version_json:
                args = self._version_json["minecraftArguments"].split(" ")

        # JVM arguments
        else:
            args = args.get("jvm", [])

            # Use common JVM arguments for old format
            if not args:
                args = JVM_ARGS_OLD

        if not args:
            logging.warning(f"No {'game' if game else 'jvm'} arguments")
            return []

        # Apply rules
        args_parsed = []
        for arg in args:
            if isinstance(arg, dict):
                if "value" not in arg and "values" not in arg:
                    logging.debug(f"Ignoring argument {arg}. No value/values specified")
                    continue
                if "rules" in arg:
                    if not rules_check(arg.get("rules", []), features=features):
                        logging.debug(f"Ignoring argument {arg}. Disallowed by rules")
                        continue

                # Value can be list or single string
                values = arg.get("value", arg.get("values"))
                if isinstance(values, list):
                    for value_ in values:
                        args_parsed.append(value_)
                else:
                    args_parsed.append(values)

            elif isinstance(arg, str):
                args_parsed.append(arg)

        return args_parsed
