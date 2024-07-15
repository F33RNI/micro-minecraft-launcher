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

import collections.abc
import json
import logging
import os
from typing import Dict, List

import requests
from dateutil import parser

from mml._version import LAUNCHER_VERSION
from mml.artifact import Artifact
from mml.download_artifact import download_artifact

# Relative to game dir
VERSIONS_DIR = "versions"

# All versions and links to their profiles
MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

# Requests timeout
TIMEOUT = 30


def update_deep(destination: Dict, update: Dict) -> Dict:
    """Recursively updates values of dictionary

    Args:
        destination (Dict): where update
        update (Dict): data to overwrite "destination"

    Returns:
        Dict: "destination" with value overwritten by "update"
    """
    for key, value in update.items():
        if isinstance(value, collections.abc.Mapping):
            destination[key] = update_deep(destination.get(key, {}), value)
        elif isinstance(value, List):
            if key not in destination:
                destination[key] = value
            else:
                destination[key].extend(value)
        else:
            destination[key] = value
    return destination


class ProfileParser:
    def __init__(self, game_dir: str):
        """Initializes ProfileParser instance

        Args:
            game_dir (str): path to parent game dir (ex. path to .minecraft)
        """
        self._game_dir = game_dir

        self._versions = []

    @property
    def game_dir(self) -> str:
        """
        Returns:
            str: path to game_dir
        """
        return self._game_dir

    @property
    def versions_dir(self) -> str:
        """
        Returns:
            str: path to versions directory (game_dir/versions)
        """
        return os.path.join(self._game_dir, VERSIONS_DIR)

    @property
    def versions_info(self) -> List[Dict]:
        """
        Returns:
            List[Dict]: output from parse_versions()
        """
        return self._versions

    def parse_versions(self) -> List[Dict]:
        """Parses versions from mojang and from VERSIONS_DIR

        Returns:
            List[Dict]: [{
                "id": "version_id",
                "type": "release" / "snapshot" / "old_alpha" / "old_beta",
                "releaseTime": "time in ISO 8601 format",
                "url": "url to download version.json (for non-local versions only)",
                "sha1": "hash of version.json (for non-local versions only)"
                "path": "path to version.json relative to versions dir",
                "local": True (for local versions only)
            }, ...]
        """
        if not os.path.exists(self._game_dir):
            logging.info(f"Creating directory {self._game_dir}")
            os.makedirs(self._game_dir)

        self._versions.clear()

        versions_dir_abs = self.versions_dir

        # Check if we have any local versions
        if not os.path.exists(versions_dir_abs):
            logging.info("No local versions found")

        # We have
        else:
            logging.info(f"Searching for versions in {versions_dir_abs}")
            for version_id in os.listdir(versions_dir_abs):
                version_dir_abs = os.path.join(versions_dir_abs, version_id)
                if not os.path.isdir(version_dir_abs):
                    continue

                # Each version must contains .json with the same name as it's directory
                version_json = os.path.join(version_dir_abs, version_id + ".json")
                if not os.path.exists(version_json):
                    continue

                # Try to parse it's JSON
                try:
                    logging.debug(f"Trying to parse {version_json}")
                    with open(version_json, "r", encoding="utf-8") as version_json_io:
                        version = json.load(version_json_io)

                    # Check required keys
                    if (
                        "id" not in version
                        or "type" not in version
                        or "releaseTime" not in version
                        or version["id"] != version_id
                    ):
                        logging.error(f"Wrong version: {version.get('id')}")
                        continue

                    # Check version
                    min_launcher_version = version.get("minimumLauncherVersion", 0)
                    if min_launcher_version > LAUNCHER_VERSION:
                        logging.debug(f"Version {version} requires launcher version {min_launcher_version}")
                        continue

                except Exception as e:
                    logging.debug("Unable to parse version's JSON", exc_info=e)
                    continue

                # Add local version
                version_ = {}
                for key in ["id", "type", "releaseTime"]:
                    version_[key] = version[key]
                version_["path"] = os.path.join(version_id, version_id + ".json")
                version_["local"] = True
                self._versions.append(version_)

            # Log number of local versions
            if self._versions:
                logging.info(f"Found {len(self._versions)} local versions")
            else:
                logging.info("No local versions found")

        # Fetch from Mojang and skip local versions
        logging.info(f"Loading versions from {MANIFEST_URL}")
        try:
            response = requests.get(MANIFEST_URL, timeout=TIMEOUT)
            if response.ok:
                manifest_versions = json.loads(response.text).get("versions", [])
                for manifest_version in manifest_versions:
                    # Check for required keys (just in case)
                    skip = False
                    for key in ["id", "type", "url", "releaseTime", "sha1"]:
                        if key not in manifest_version:
                            skip = True
                            break
                    if skip:
                        logging.warning(f"Wrong version fetched from Mojang: {manifest_version}")
                        continue

                    # Ignore if local
                    if self.version_path_by_id(manifest_version["id"], download=False):
                        logging.debug(f"Skipping {manifest_version['id']}. Local version exists")
                        continue

                    # Build path and add to the list
                    manifest_version["path"] = os.path.join(manifest_version["id"], manifest_version["id"] + ".json")
                    self._versions.append(manifest_version)
            else:
                logging.error(f"Unable to fetch versions: {response.status_code} - {response.text}")
        except Exception as e:
            logging.error(f"Unable to fetch versions: {e}")
            logging.debug("Error details", exc_info=e)

        # Sort by release time
        self._versions = sorted(self._versions, key=lambda d: parser.parse(d["releaseTime"]), reverse=True)

        return self._versions

    def parse_version_json(self, path_to_json: str) -> Dict or None:
        """Parses and recursively inherits version's JSON
        Call parse_versions() before

        Args:
            path_to_json (str): relative path to version's JSON from parse_versions()

        Returns:
            Dict or None: parsed and inherited version's JSON or None if unable to find inherited JSON
        """
        path_to_json = os.path.join(self.versions_dir, path_to_json)
        logging.debug(f"Parsing {path_to_json}")
        with open(path_to_json, "r", encoding="utf-8") as version_json_io:
            version_json = json.load(version_json_io)

        # Check version
        min_launcher_version = version_json.get("minimumLauncherVersion", 0)
        if min_launcher_version > LAUNCHER_VERSION:
            logging.error(f"Unable to load version. Required launcher version: {min_launcher_version}")
            return None

        # Inherit from other version
        if "inheritsFrom" in version_json:
            inherits_from = version_json["inheritsFrom"]
            logging.debug(f"Inheriting JSON from {inherits_from}")
            inherits_from_json = self.version_path_by_id(inherits_from, download=True)
            if not inherits_from_json:
                logging.error(f"Unable to fetch required version {inherits_from}")
                return None
            inherited_json = self.parse_version_json(inherits_from_json)

            # Override inherited data with current one
            version_json = update_deep(inherited_json, version_json)

        return version_json

    def version_path_by_id(self, version_id: str, download: bool) -> str or None:
        """Returns path to JSON file relative to versions dir or downloads it from mojang based on version ID
        NOTE: Call parse_versions() before

        Args:
            version_id (str): version ID from parse_versions()
            download (bool): True to try to download version.json from Mojang if not found locally

        Returns:
            str or None: path to JSON file relative to versions dir or None in case of error
        """
        version_info = None
        for version_info_ in self._versions:
            if version_info_["id"] == version_id:
                version_info = version_info_
        if not version_info:
            return None

        # Download from Mojang
        if not version_info.get("local"):
            if not download:
                return None
            version_artifact = Artifact(version_info, parent_dir=self.versions_dir)
            if not download_artifact(version_artifact):
                return None

        return version_info["path"]
