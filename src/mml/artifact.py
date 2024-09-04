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

# For calculating checksum
CHUNK_SIZE = 8192

# Default artifact url if none is specified
URL_DEFAULT = "https://libraries.minecraft.net/"


class Artifact:
    def __init__(
        self,
        artifact: dict,
        parent_dir: str,
        target_file: str | None = None,
        unpack_into: str | None = None,
        exclude_files: list[str] | None = None,
        copy_to: str | None = None,
    ):
        """Initializes Artifact instance. This class in a wrapper and container for artifact from JSON

        Args:
            artifact (dict): artifact's JSON as dictionary
            parent_dir (str): artifact's parent dir
            target_file (str | None): path to artifact file (relative to parent_dir) to overwrite artifact["path"]
            unpack_into (str | None, optional): path to unpack file after downloading it. Defaults to None
            exclude_files (list[str] | None, optional): list of files to exclude while unpacking. Defaults to None
            copy_to (str | None): copy downloaded file to another file
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
            package_name_version = self._artifact["name"].split(":")
            if len(package_name_version) != 3:
                logging.warning(f"Unknown artifact name format: {self._artifact['name']}")
            else:
                package = "/".join(package_name_version[0].split("."))
                name = package_name_version[1]
                version = package_name_version[2]
                uri_from_name = f"{package}/{name}/{version}/{name}-{version}"

                # Split extension (just in case) i think this will never be useful and may be even wrong :)
                ext = ".jar"
                for ext_ in [".jar", ".zip", ".dll", ".so"]:
                    if uri_from_name.endswith(ext_):
                        ext = ext_
                        uri_from_name = uri_from_name[: -len(ext_)]
                        break

                # Set this as path
                self._artifact["path"] = uri_from_name + ext

                # VERY old format
                if "url" not in self._artifact:
                    self._artifact["url"] = URL_DEFAULT

                # Fix for old forge versions
                if package == "net/minecraftforge":
                    uri_from_name += "-universal"

                # Append to the url
                if not self._artifact["url"].endswith("/"):
                    self._artifact["url"] += "/"
                self._artifact["url"] += uri_from_name + ext

    @property
    def parent_dir(self) -> str:
        """
        Returns:
            str: artifact's parent dir
        """
        return self._parent_dir

    @property
    def unpack_into(self) -> str | None:
        """
        Returns:
            str | None: path to unpack file after downloading it or None if not specified
        """
        return self._unpack_into

    @property
    def exclude_files(self) -> list[str] | None:
        """
        Returns:
            list[str] | None: list of files to exclude while unpacking or None if not specified
        """
        return self._exclude_files

    @property
    def copy_to(self) -> str | None:
        """
        Returns:
            str | None: copy downloaded file to another file
        """
        return self._copy_to

    @property
    def path(self) -> str | None:
        """
        Returns:
            str | None: artifact["path"] or target_file or None if none of them defined
        """
        return self._artifact.get("path")

    @property
    def url(self) -> str | None:
        """
        Returns:
            str | None: artifact["url"] or None if no URL
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

    def verify_checksum(self) -> bool:
        """Calculate artifact's checksum

        Returns:
            bool: True if artifact doesn't have a checksum or it's checksum is valid or False if not
        """
        if not self.artifact_exists:
            logging.debug("Unable to calculate checksum. No artifact or it doesn't exist")
            return True

        # [(alg, checksum), ...]
        allowed_checksums = []
        for alg in ["sha1", "md5", "sha256", "sha512"]:
            if alg in self._artifact:
                allowed_checksums.append((alg, self._artifact[alg]))

        # Idk think we can face this but just in case
        if "checksum" in self._artifact and isinstance(self._artifact["checksum"], str):
            allowed_checksums.append(("sha1", self._artifact["checksum"]))

        # Very old format
        if "checksums" in self._artifact:
            if isinstance(self._artifact["checksums"], list):
                for checksum in self._artifact["checksums"]:
                    allowed_checksums.append(("sha1", checksum))

        # Return True if no checksums available
        if len(allowed_checksums) == 0:
            logging.warning(f"No checksums for {self._artifact.get('name', str(self._artifact))} artifact")
            return True

        # Verify
        for alg, checksum in allowed_checksums:
            if alg == "sha1":
                file_hash = hashlib.sha1(usedforsecurity=False)
            elif alg == "md5":
                file_hash = hashlib.md5(usedforsecurity=False)
            elif alg == "sha256":
                file_hash = hashlib.sha256(usedforsecurity=False)
            elif alg == "sha512":
                file_hash = hashlib.sha512(usedforsecurity=False)
            else:
                logging.error(f"Unknown checksum algorithm: {alg}")
                return False

            artifact_path = os.path.join(self._parent_dir, self._artifact["path"])
            with open(artifact_path, "rb") as artifact_io:
                chunk = artifact_io.read(CHUNK_SIZE)
                while chunk:
                    file_hash.update(chunk)
                    chunk = artifact_io.read(CHUNK_SIZE)

            checksum_ = file_hash.hexdigest()
            logging.debug(f"Calculated {alg} checksum: {checksum_}")

            if checksum_.lower() == checksum.lower():
                logging.debug("Checksum is valid")
                return True

        logging.warning(f"Wrong checksum of {self._artifact.get('name', str(self._artifact))} artifact")
        return False
