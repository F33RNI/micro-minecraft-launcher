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
from typing import Dict, List

# For calculating checksum
CHUNK_SIZE = 8192


class Artifact:
    def __init__(
        self,
        artifact: Dict,
        parent_dir: str,
        target_file: str or None = None,
        unpack_into: str or None = None,
        exclude_files: List[str] or None = None,
        copy_to: str or None = None,
    ):
        """Initializes Artifact instance. This class in a wrapper and container for artifact from JSON

        Args:
            artifact (Dict): artifact's JSON as dictionary
            parent_dir (str): artifact's parent dir
            target_file (str or None): path to artifact file (relative to parent_dir) to overwrite artifact["path"]
            unpack_into (str or None, optional): path to unpack file after downloading it. Defaults to None
            exclude_files (List[str] or None, optional): list of files to exclude while unpacking. Defaults to None
            copy_to (str or None): copy downloaded file to another file
        """
        self._artifact = artifact.copy()
        self._parent_dir = parent_dir
        self._unpack_into = unpack_into
        self._exclude_files = exclude_files
        self._copy_to = copy_to

        if target_file:
            self._artifact["path"] = target_file

        # Old style
        # Ex.: net.fabricmc:sponge-mixin:0.13.3+mixin.0.8.5 ->
        # net/fabricmc/sponge-mixin/0.13.3+mixin.0.8.5/sponge-mixin-0.13.3+mixin.0.8.5.jar
        if "path" not in self._artifact and "name" in self._artifact:
            package_name_version = self._artifact["name"].split[":"]
            if len(package_name_version) != 3:
                logging.warning(f"Unknown artifact name format: {self._artifact['name']}")
            else:
                package = package_name_version[0]
                name = package_name_version[1]
                version = package_name_version[2]
                uri_from_name = f"{package}/{name}/{version}/{name}-{version}"
                if (
                    not uri_from_name.endswith(".jar")
                    and not uri_from_name.endswith(".zip")
                    and not uri_from_name.endswith(".dll")
                    and not uri_from_name.endswith(".so")
                ):
                    uri_from_name += ".jar"

                self._artifact["path"] = uri_from_name

                if "url" in self._artifact:
                    if not self._artifact["url"].endswith("/"):
                        self._artifact["url"] += "/"
                    self._artifact["url"] += uri_from_name

    @property
    def parent_dir(self) -> str:
        """
        Returns:
            str: artifact's parent dir
        """
        return self._parent_dir

    @property
    def unpack_into(self) -> str or None:
        """
        Returns:
            str or None: path to unpack file after downloading it or None if not specified
        """
        return self._unpack_into

    @property
    def exclude_files(self) -> List[str] or None:
        """
        Returns:
            List[str] or None: list of files to exclude while unpacking or None if not specified
        """
        return self._exclude_files

    @property
    def copy_to(self) -> str or None:
        """
        Returns:
            str or None: copy downloaded file to another file
        """
        return self._copy_to

    @property
    def path(self) -> str or None:
        """
        Returns:
            str or None: artifact["path"] or target_file or None if none of them defined
        """
        return self._artifact.get("path")

    @property
    def url(self) -> str or None:
        """
        Returns:
            str or None: artifact["url"] or None if no URL
        """
        return self._artifact.get("url")

    @property
    def size(self) -> int:
        """
        Returns:
            int: size of artifact in bytes or 0 if not defined
        """
        return self._artifact.get("size", 0)

    @property
    def checksum_alg(self) -> str or None:
        """Searches for checksum algorithm in artifact

        Returns:
            str or None: "sha1", "md5", "sha256", "sha512" or None if not found
        """
        for alg in ["sha1", "md5", "sha256", "sha512"]:
            if alg in self._artifact:
                return alg
        return None

    @property
    def target_checksum(self) -> str or None:
        """Value of checksum (value of checksum_alg)

        Returns:
            str or None: checksum or None if not found
        """
        alg = self.checksum_alg
        if not alg:
            return None
        return self._artifact[alg]

    @property
    def artifact_exists(self) -> bool:
        """Checks if target file exists

        Returns:
            bool: True if self._parent_dir/self._artifact["path"] exists
        """
        if not "path" in self._artifact:
            return False
        artifact_path = os.path.join(self._parent_dir, self._artifact["path"])
        if not os.path.exists(artifact_path):
            return False
        return True

    def calculate_actual_checksum(self) -> str or None:
        """Calculate artifact's checksum

        Returns:
            str or None: artifact's checksum (checksum_alg) or None if not exists
        """
        if not self.artifact_exists:
            logging.debug("Unable to calculate checksum. No artifact or it doesn't exist")
            return None

        alg = self.checksum_alg
        if not alg:
            logging.debug("Unable to calculate checksum. Unknown algorithm")
            return None

        if alg == "sha1":
            file_hash = hashlib.sha1(usedforsecurity=False)
        elif alg == "md5":
            file_hash = hashlib.md5(usedforsecurity=False)
        elif alg == "sha256":
            file_hash = hashlib.sha256(usedforsecurity=False)
        elif alg == "sha512":
            file_hash = hashlib.sha512(usedforsecurity=False)
        else:
            raise Exception("Unknown algorithm")

        artifact_path = os.path.join(self._parent_dir, self._artifact["path"])
        with open(artifact_path, "rb") as artifact_io:
            chunk = artifact_io.read(CHUNK_SIZE)
            while chunk:
                file_hash.update(chunk)
                chunk = artifact_io.read(CHUNK_SIZE)

        checksum = file_hash.hexdigest()
        logging.debug(f"Calculated {alg} checksum: {checksum}")
        return checksum
