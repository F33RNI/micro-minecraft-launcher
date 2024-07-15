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

import glob
import logging
import os
import re
import subprocess

import jdk

from mml.rules_check import os_name

# Main subdir
JDK_PATH = "jdk"

# Relative to JDK_PATH
JAVA_PATH = os.path.join("jdk*", "bin", "java")


def classpath_separator() -> str:
    """
    Returns:
        str: Java classpath separator
    """
    if os_name() == "windows":
        return ";"
    else:
        return ":"


def jdk_check_install(version: int = 17) -> str or None:
    """Check if Java exists and installs it if not

    Args:
        version (int, optional): major version to download. Defaults to 17

    Returns:
        str or None: java executable path or None in case of error
    """
    # Target subdir
    jdk_path_abs = os.path.abspath(JDK_PATH)

    # Create subdir if not exists
    if not os.path.exists(jdk_path_abs):
        logging.info(f"Creating {jdk_path_abs} directory")
        os.makedirs(jdk_path_abs)

    java_final_path = os.path.join(jdk_path_abs, JAVA_PATH)
    java_paths = glob.glob(java_final_path)

    logging.debug(f"Found java executables: {'; '.join(java_paths)}")

    # Check if we need to download
    for java_path in java_paths:
        java_version = _parse_major_version(java_path)
        if java_version == version:
            logging.info(f"Java path: {java_path}")
            return java_path

    # Download and install
    logging.warning(f"Installing JRE {version} into {jdk_path_abs}")
    try:
        jdk.install(version=str(version), jre=True, path=jdk_path_abs)
    except Exception as e:
        logging.warning(f"Unable to install JRE {version}: {e}. Trying JDK {version}")
        logging.debug("Error details", exc_info=e)
        jdk.install(version=str(version), jre=False, path=jdk_path_abs)

    # Check again
    java_paths = glob.glob(java_final_path)
    for java_path in java_paths:
        if _parse_major_version(java_path) == version:
            logging.info(f"Java path: {java_path}")
            return java_path

    logging.error("Unable to download Java")
    return None


def _parse_major_version(java_bin: str) -> int or None:
    """Parses major java version by running java -version

    Args:
        java_bin (str): path to java executable

    Returns:
        int: major version or -1 in case of error
    """
    cmd = [java_bin, "-version"]
    logging.debug(f"Running {' '.join(cmd)}")
    java_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)

    out, err = java_process.communicate()
    out = out.decode("utf-8", errors="replace").strip()
    err = err.decode("utf-8", errors="replace").strip()

    version_out = (out + err).split(" ")
    for version_word in version_out:
        version_word = version_word.strip()
        if not version_word:
            continue

        try:
            version = re.search("[0-9]+\\.[0-9]+\\..*", version_word).group(0)
        except (AttributeError, IndexError):
            continue
        if not version:
            continue

        logging.debug(f"Raw java version: {version}")

        if version.startswith("1.8"):
            version = 8
        else:
            version = int(version.split(".")[0])

        logging.debug(f"Found java version: {version}")
        return version

    return -1
