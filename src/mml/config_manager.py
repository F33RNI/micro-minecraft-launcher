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

import argparse
import json
import logging
import os
from typing import Any

from mml._version import __version__
from mml.rules_check import os_name


def get_default_game_dir(os_name_: str) -> str:
    """
    Args:
        os_name_ (str): "linux", "windows" or "osx"

    Returns:
        str: path to .minecraft on different OS
    """
    if os_name_ == "linux":
        return os.path.join(os.path.expanduser("~"), ".minecraft")
    elif os_name_ == "windows":
        return os.path.join(os.getenv("APPDATA"), ".minecraft")
    elif os_name_ == "osx":
        os.path.join(os.path.expanduser("~"), "Library", "Application Support", ".minecraft")


CONFIG_DEFAULT = {"game_dir": get_default_game_dir(os_name()), "resolver_processes": 4}


class ConfigManager:
    def __init__(self, config_file: str, args: argparse.Namespace) -> None:
        """Initializes ConfigManager and reads config file

        Args:
            config_file (str): config file (.json)
            args (argparse.Namespace): cli arguments
        """
        self._config_file = config_file

        self._config = {}

        # Convert args to dict
        self._args_d = vars(args)

        # Try to load config file
        if os.path.exists(config_file):
            logging.debug(f"Loading {config_file}")
            with open(config_file, encoding="utf-8", errors="replace") as config_file_io:
                json_content = json.load(config_file_io)
                if json_content is not None and isinstance(json_content, dict):
                    self._config = json_content
                else:
                    logging.warning(f"Unable to load config from {config_file}")
        else:
            logging.warning(f"File {config_file} doesn't exist")

    def get(self, key: str, default_value: Any or None = None, ignore_args: bool = False) -> Any:
        """Retrieves value from args or config by key
        Priority: args -> config -> CONFIG_DEFAULT -> default_value

        Args:
            key (str): config key to get value of
            default_value (Any or None): value to return if key doesn't exists even in CONFIG_DEFAULT
            ignore_args (bool or None, optional): True to ignore self._args_d

        Returns:
            Any: key's value or default_value
        """
        sources = [self._config, CONFIG_DEFAULT] if ignore_args else [self._args_d, self._config, CONFIG_DEFAULT]
        for source in sources:
            value = source.get(key)
            if value is not None:
                return value

        logging.debug(f"Key {key} doesn't exist in arguments, config or CONFIG_DEFAULT")
        return default_value

    def set(self, key: str, value: Any) -> None:
        """Updates config values and saves it to the file

        Args:
            key (str): config key
            value (Any): key's value
        """
        # Set value
        self._config[key] = value

        # Save to file
        logging.debug(f"Saving config to {self._config_file}")
        with open(self._config_file, "w+", encoding="utf-8") as config_file_io:
            json.dump(self._config, config_file_io, indent=4, ensure_ascii=False)
