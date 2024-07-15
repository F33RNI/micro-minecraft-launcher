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
import logging
import multiprocessing
import shlex
import sys
import time
from typing import Dict, List

from mml._version import __version__
from mml.config_manager import CONFIG_DEFAULT, ConfigManager
from mml.downloader import Downloader
from mml.launcher import Launcher, State
from mml.logging_handler import LoggingHandler, worker_configurer
from mml.profile_parser import ProfileParser
from mml.rules_check import os_name

CONFIG_FILE_DEFAULT_PATH = ".micro-minecraft-launcher.json"

EXAMPLE_USAGE = """examples:
  micro-minecraft-launcher --list-versions
  micro-minecraft-launcher 1.21
  micro-minecraft-launcher --isolate 1.18.2
  micro-minecraft-launcher --config /path/to/custom/micro-minecraft-launcher.json
  micro-minecraft-launcher -d /path/to/custom/minecraft -j="-Xmx6G" -g="--server 192.168.0.1" 1.21
  micro-minecraft-launcher -j="-Xmx4G" -g="--width 800 --height 640" 1.18.2
"""


def parse_args() -> argparse.Namespace:
    """Parses cli arguments

    Returns:
        argparse.Namespace: parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Simple cross-platform cli launcher for Minecraft",
        epilog=EXAMPLE_USAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=False,
        default=CONFIG_FILE_DEFAULT_PATH,
        help=f"path to config file (Default: {CONFIG_FILE_DEFAULT_PATH})",
    )
    parser.add_argument(
        "-d",
        "--game-dir",
        type=str,
        required=False,
        default=None,
        help=f"path to .minecraft (Default: {CONFIG_DEFAULT['game_dir']})",
    )
    parser.add_argument(
        "-l",
        "--list-versions",
        action="store_true",
        default=False,
        help="print online (official), local versions and exit",
    )
    parser.add_argument(
        "-u",
        "--user",
        type=str,
        required=False,
        default=None,
        help="player's username",
    )
    parser.add_argument(
        "--auth-uuid",
        type=str,
        required=False,
        default=None,
        help="player's UUID (Default: offline UUID from username)",
    )
    parser.add_argument(
        "--auth-access-token",
        type=str,
        required=False,
        default=None,
        help="Mojang Access Token or the final token in the Microsoft authentication scheme",
    )
    parser.add_argument(
        "--user-type",
        type=str,
        required=False,
        default=None,
        help='"msa" for Microsoft Authentication Scheme,'
        ' "legacy" for Legacy Minecraft Authentication and'
        ' "mojang" for Legacy Mojang Authentication (Default: mojang)',
    )
    parser.add_argument(
        "-i",
        "--isolate",
        action="store_true",
        default=False,
        help='put "saves", "logs" and all other profile data inside versions/version_id directory instead of game_dir',
    )
    parser.add_argument(
        "--java-path",
        type=str,
        required=False,
        default=None,
        help="custom path to java binary (Default: download locally)",
    )
    parser.add_argument(
        "-e",
        "--env-variables",
        metavar="KEY=VALUE",
        nargs="+",
        required=False,
        help="env variable(s) for final command as key=value pairs"
        " (Ex.: -e version_type=snapshot launcher_name=custom-launcher)"
        ' NOTE: If a value contains spaces, you should define it with double quotes: launcher_name="Custom launcher"'
        " NOTE: Values are always treated as strings"
        ' NOTE: Will merge "env_variables" from config file and overwrite same variables',
    )
    parser.add_argument(
        "-j",
        "--jvm-args",
        type=str,
        required=False,
        default=None,
        help='extra arguments for Java separated with spaces (Ex.: -j="-Xmx6G -XX:G1NewSizePercent=20")'
        " NOTE: You should define it with double quotes as in example"
        " NOTE: If an argument contains spaces, you should define it with double quotes: -j '-foo \"multiple words\"'"
        ' NOTE: Will append to the bottom of "game_args" from config file',
    )
    parser.add_argument(
        "-g",
        "--game-args",
        type=str,
        required=False,
        default=None,
        help='extra arguments for Minecraft separated with spaces (Ex.: -g="--server 192.168.0.1 --port 25565")'
        " NOTE: You should define it with double quotes as in example"
        " NOTE: If an argument contains spaces, you should define it with double quotes: -g '-foo \"multiple words\"'"
        ' NOTE: Will append to the bottom of "game_args" from config file',
    )
    parser.add_argument(
        "--downloader-processes",
        type=int,
        required=False,
        default=None,
        help=f"number of processes to download files (Default: {CONFIG_DEFAULT['downloader_processes']})",
    )
    parser.add_argument(
        "id",
        nargs="?",
        default=None,
        help="minecraft version to launch. Run with --list-versions to see available versions",
    )

    parser.add_argument("--verbose", action="store_true", default=False, help="debug logs")
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="show launcher's version number and exit",
    )

    return parser.parse_args()


def print_versions(profile_parser_: ProfileParser) -> None:
    """Prints local and Mojang versions to console

    Args:
        profile_parser_ (ProfileParser): ProfileParser instance
    """
    versions = profile_parser_.parse_versions()
    versions_log = []
    for version in versions:
        versions_log.append(version["id"] + ("*" if version.get("local") else ""))
    logging.info(f"Available versions (* - local): {', '.join(versions_log)}")


def username_dialog() -> str or None:
    """Asks user for username

    Returns:
        str or None: username or None if not provided
    """
    logging.debug("Asking for username")

    # Sleep a bit to make sure logs are flushed
    time.sleep(0.1)
    print("\n" + "#" * 80 + "\n", flush=True)
    username = input("USERNAME: ").strip()
    print("\n" + "#" * 80 + "\n", flush=True)
    if not username:
        logging.warning("No username provided")
        return None

    logging.info(f"Entered username: {username}")
    return username


def key_value_pairs_to_dict(key_values: List[str] or None, separator: str = "=") -> Dict:
    """Converts key-value pairs (from arguments) into dictionary

    Args:
        key_values (List[str] or None): ex.: ["version_type=snapshot", "launcher_name=custom-launcher"]
        separator (str, optional): key and value(s) separator. Defaults to "="
        NOTE: Values are always treated as strings

    Returns:
        Dict: ex.: {"version_type": "snapshot", "launcher_name": "custom-launcher"}
    """
    result = {}
    if key_values:
        for key_value in key_values:
            items = key_value.split(separator)
            key = items[0].strip()
            value = None
            if len(items) > 1:
                # Rejoin the rest
                value = separator.join(items[1:])
            result[key] = value
    return result


def main():
    """Main entry"""
    # Multiprocessing fix for Windows
    if sys.platform.startswith("win"):
        multiprocessing.freeze_support()

    args = parse_args()
    launcher_ = None

    # Initialize logging and start logging listener as process
    logging_handler_ = LoggingHandler(verbose=args.verbose)
    logging_handler_process = multiprocessing.Process(target=logging_handler_.configure_and_start_listener)
    logging_handler_process.start()
    worker_configurer(logging_handler_.queue_)

    downloader_ = None
    try:
        # Log software version and GitHub link
        logging.info(f"micro-minecraft-launcher version: {__version__}")
        logging.info("https://github.com/F33RNI/micro-minecraft-launcher")

        # Detect OS, check and log it
        os_name_ = os_name()
        logging.info(f"Detected OS: {os_name_}")

        config_manager_ = ConfigManager(args.config, args)

        # Log minecraft dir
        game_dir = config_manager_.get("game_dir")
        logging.info(f"Game directory: {game_dir}")
        profile_parser_ = ProfileParser(game_dir)

        # Print available versions and exit
        if args.list_versions:
            print_versions(profile_parser_)
            logging_handler_.queue_.put(None)
            return

        # Check if have anything to launch
        version_id = config_manager_.get("id")
        if version_id:
            logging.info(f"Version ID: {version_id}")

            downloader_ = Downloader(config_manager_.get("downloader_processes"), logging_handler_.queue_)

            username = config_manager_.get("user")
            if not username:
                username = username_dialog()
            auth_uuid = config_manager_.get("auth_uuid")
            auth_access_token = config_manager_.get("auth_access_token")
            user_type = config_manager_.get("user_type")
            isolate_profile = config_manager_.get("isolate_profile", ignore_args=True)
            if args.isolate:
                isolate_profile = True
            java_path = config_manager_.get("java_path")

            # Save for future sessions
            if version_id is not None:
                config_manager_.set("id", version_id)
            if username is not None:
                config_manager_.set("user", username)
            if auth_uuid is not None:
                config_manager_.set("auth_uuid", auth_uuid)
            if auth_access_token is not None:
                config_manager_.set("auth_access_token", auth_access_token)
            if user_type is not None:
                config_manager_.set("user_type", user_type)
            if isolate_profile is not None:
                config_manager_.set("isolate_profile", isolate_profile)
            if java_path is not None:
                config_manager_.set("java_path", java_path)

            # Get extra env variables from config or from cli arguments
            env_variables = config_manager_.get("env_variables", {}, ignore_args=True)
            env_variables.update(key_value_pairs_to_dict(args.env_variables))
            logging.info(f"Extra env variables: {env_variables}")

            # Get extra JVM args from config or from cli arguments
            extra_jvm_args = config_manager_.get("jvm_args", [], ignore_args=True)
            if args.jvm_args:
                for jvm_arg in shlex.split(args.jvm_args, posix=True):
                    extra_jvm_args.append(jvm_arg)
            logging.info(f"Extra JVM arguments: {' '.join(extra_jvm_args)}")

            # Get extra game (minecraft) args from config or from cli arguments
            extra_game_args = config_manager_.get("game_args", [], ignore_args=True)
            if args.game_args:
                for game_arg in shlex.split(args.game_args, posix=True):
                    extra_game_args.append(game_arg)
            logging.info(f"Extra game (Minecraft) arguments: {' '.join(extra_game_args)}")

            launcher_ = Launcher(
                downloader_,
                profile_parser_,
                version_id,
                env_variables=env_variables,
                features=config_manager_.get("features"),
                user_name=username,
                auth_uuid=auth_uuid,
                auth_access_token=auth_access_token,
                user_type=user_type,
                isolate_profile=isolate_profile,
                java_path=java_path,
                extra_jvm_args=extra_jvm_args,
                extra_game_args=extra_game_args,
            )
            launcher_.start()

            while launcher_.state != State.IDLE and launcher_.state != State.ERROR:
                time.sleep(1)

        # No version to launch provided
        else:
            logging.warning("Nothing to launch. Exiting...")

    # Catch SIGTERM and Ctrl+C
    except (SystemExit, KeyboardInterrupt):
        logging.warning("Interrupted")
        if launcher_:
            launcher_.stop()

    # Catch other errors to exit gracefully
    except Exception as e:
        logging.error(e, exc_info=e)

    # Stop all downloads
    if downloader_ is not None:
        downloader_.stop(stop_background_thread=True)

    # Finally, stop logging loop
    logging.info("micro-minecraft-launcher exited")
    logging_handler_.queue_.put(None)


if __name__ == "__main__":

    main()
