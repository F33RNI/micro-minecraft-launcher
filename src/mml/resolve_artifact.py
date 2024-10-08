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
import os
import shutil
import time
from zipfile import ZipFile

import requests

from mml.artifact import Artifact

# For downloading file from stream
CHUNK_SIZE = 8192

# Requests timeout
TIMEOUT = 240

# How many download attempts are allowed (1 - no retries)
DOWNLOAD_ATTEMPTS = 3

# Delay between attempts
ATTEMPT_DELAY = 1.0


def resolve_artifact(artifact_: Artifact, _attempt: int = 0, verify_checksums: bool = True) -> str | None:
    """Checks if artifact exists (and verifies it's checksum) and downloads it if not
    Also, copies and unpacks it if needed

    Args:
        artifact_ (Artifact): artifact instance to download, copy and unpack
        verify_checksums (bool, optional): False to ignore checksum mismatch. Defaults to True

    Returns:
        str | None: path to artifact if exists or downloaded successfully or None in case of error
    """
    if artifact_.artifact_exists and (not verify_checksums or artifact_.verify_checksum()):
        artifact_path = os.path.join(artifact_.parent_dir, artifact_.path)
        logging.debug(f"Artifact {artifact_path} exists")
        unpack_copy(artifact_, artifact_path)
        return artifact_path

    if not artifact_.url:
        logging.warning("Unable to download artifact. No url specified")
        return None

    if not artifact_.path:
        logging.warning("Unable to download artifact. No target path specified")
        return None

    artifact_path = os.path.join(artifact_.parent_dir, artifact_.path)
    artifact_dir = os.path.dirname(artifact_path)

    if not os.path.exists(artifact_dir):
        logging.debug(f"Creating {artifact_dir} directory")
        os.makedirs(artifact_dir)

    # Download
    _attempt += 1
    logging.info(f"Downloading {os.path.basename(artifact_path)} from {artifact_.url}")
    try:
        response = requests.get(artifact_.url, timeout=TIMEOUT, stream=True)
        if response.ok:
            with open(artifact_path, "wb") as artifact_io:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        artifact_io.write(chunk)
                artifact_io.flush()
                os.fsync(artifact_io.fileno())
        else:
            logging.error(f"Unable to download artifact from {artifact_.url}: {response.status_code}-{response.text}")
    except Exception as e:
        logging.error(f"Unable to download artifact from {artifact_.url}: {e}")
        logging.debug("Error details", exc_info=e)

    # Check
    if not artifact_.artifact_exists or (verify_checksums and not artifact_.verify_checksum()):
        # Wait a bit and try again
        if _attempt < DOWNLOAD_ATTEMPTS:
            time.sleep(ATTEMPT_DELAY)
            logging.info(f"Trying to download again {_attempt + 1} / {DOWNLOAD_ATTEMPTS}")
            return resolve_artifact(artifact_, _attempt=_attempt)

        # No more tries
        else:
            logging.info(f"Tried {_attempt} times. Giving up...")
            return None

    logging.debug("Artifact downloaded successfully")

    if not unpack_copy(artifact_, artifact_path):
        return None

    return artifact_path


def unpack_copy(artifact_: Artifact, artifact_path: str) -> bool:
    """Unpacks and copies artifact if needed

    Args:
        artifact_ (Artifact): artifact instance
        artifact_path (str): path to downloaded artifact

    Returns:
        bool: False in case of error
    """
    # Unpack it if needed without some files
    if artifact_.unpack_into:
        logging.debug(f"Unpacking {artifact_path} into {artifact_.unpack_into}")
        try:
            with ZipFile(artifact_path, "r") as zip_io:
                file_list = zip_io.namelist()
                for file in file_list:
                    exclude = False
                    for exclude_file in artifact_.exclude_files:
                        if file.startswith(exclude_file):
                            exclude = True
                            break
                    if exclude:
                        continue
                    zip_io.extract(file, artifact_.unpack_into)
        except Exception as e:
            logging.error(f"Unable to unpack {artifact_path}: {e}")
            logging.debug("Error details", exc_info=e)
            return False

    # Copy if needed
    if artifact_.copy_to and not os.path.exists(artifact_.copy_to):
        try:
            copy_to_dir = os.path.dirname(artifact_.copy_to)
            if not os.path.exists(copy_to_dir):
                logging.debug(f"Creating {copy_to_dir} directory")
                os.makedirs(copy_to_dir, exist_ok=True)

            logging.debug(f"Copying {artifact_path} into {artifact_.copy_to}")
            shutil.copyfile(artifact_path, artifact_.copy_to)

        except Exception as e:
            logging.error(f"Unable to copy {artifact_path} into {artifact_.copy_to}: {e}")
            logging.debug("Error details", exc_info=e)
            return False

    # Seems OK
    return True
