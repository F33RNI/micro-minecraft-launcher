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
import platform
import re
import sys
from typing import Dict, List


def os_name() -> str:
    """
    Returns:
        str: "windows" / "linux" / "osx"

    Raises:
        Exception: in case of other platform
    """
    if "linux" in sys.platform:
        return "linux"
    elif "win32" in sys.platform or "cygwin" in sys.platform:
        return "windows"
    elif "darwin" in sys.platform:
        return "osx"
    else:
        raise Exception(f"Unsupported OS: {sys.platform}")


def rules_check(rules: List[Dict], features: Dict or None = None) -> bool:
    """Tests rules (for accepting arguments or libs)
    <https://minecraft.fandom.com/wiki/Client.json>

    Args:
        rules (List[Dict]): ex.: [
            {
                "action": "allow"
            },
            {
                "action": "disallow",
                "os": {
                    "name": "osx"
                }
            }
        ]
        features (Dict or None, optional): {
            "is_demo_user": value,
            "has_custom_resolution": value
            "has_quick_plays_support": value,
            "is_quick_play_singleplayer": value,
            "is_quick_play_multiplayer": value,
            "is_quick_play_realms": value
        }

    Returns:
        bool: True if "allow", False if "disallow". True if no rules provided
    """
    if not rules or len(rules) == 0:
        logging.debug("Empty rules")
        return True

    if features is None:
        features = {}

    result = None

    # From top to bottom
    for rule in rules:
        if "action" not in rule:
            continue
        is_allowed = rule["action"] == "allow"

        # Check os conditions
        os_result = None
        if "os" in rule:

            if "name" in rule["os"]:
                os_result = rule["os"]["name"] == os_name()

            # AND
            if (os_result is None or os_result is True) and "arch" in rule["os"]:
                current_arch = platform.machine().lower()
                if rule["os"]["arch"] == current_arch:
                    if os_result is None:
                        os_result = True
                else:
                    os_result = False

            # AND
            if (os_result is None or os_result is True) and "version" in rule["os"]:
                if os_name().startswith("win"):
                    current_version = platform.win32_ver()[1]
                elif os_name() == "osx":
                    current_version = platform.mac_ver()[0]
                else:
                    current_version = platform.release().lower()

                if re.match(rule["os"]["version"], current_version):
                    if os_result is None:
                        os_result = True
                else:
                    os_result = False

        # Check features conditions
        features_result = None
        if "features" in rule:
            for key, value in rule["features"].items():
                if key not in features:
                    continue
                if features[key] == value:
                    if features_result is None:
                        features_result = True
                elif features_result:
                    features_result = False
                    break
            if features_result is None:
                features_result = False

        # No conditions -> just accept what we have
        if os_result is None and features_result is None:
            result = is_allowed

        # Value applied only if all conditions are met or unknown
        elif (os_result is None or os_result is True) and (features_result is None or features_result is True):
            result = is_allowed

        # Invert if one of condition if False
        elif result is None:
            result = not is_allowed

    if result is None:
        result = False
    return result
