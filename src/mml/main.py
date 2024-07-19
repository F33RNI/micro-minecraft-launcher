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
import glob
import json
import logging
import multiprocessing
import os
import shlex
import shutil
import subprocess
import sys
import time
from typing import Dict, List
from uuid import uuid4

import certifi
import requests

from mml._version import __version__
from mml.config_manager import CONFIG_DEFAULT, ConfigManager
from mml.file_resolver import FileResolver
from mml.jdk_check_install import jdk_check_install
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
  micro-minecraft-launcher --write-profiles
  micro-minecraft-launcher --write-profiles --run-before java -jar forge-1.18.2-40.2.4-installer.jar --delete-files forge*.jar
"""

LAUNCHER_PROFILES_FILE = "launcher_profiles.json"
LAUNCHER_PROFILES_ICON_DEFAULT = "Grass"

# For update checking
TIMEOUT = 30


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
        ' NOTE: Will append to the bottom of "jvm_args" from config file',
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
        "--resolver-processes",
        type=int,
        required=False,
        default=None,
        help="number of processes to resolve (download, copy and unpack) files"
        f"(Default: {CONFIG_DEFAULT['resolver_processes']})",
    )
    parser.add_argument(
        "--write-profiles",
        action="store_true",
        default=False,
        help="write all found local versions into game_dir/launcher_profiles.json (useful for installing Forge/Fabric)",
    )
    parser.add_argument(
        "--run-before",
        type=str,
        required=False,
        default=None,
        help="run specified command before launching game (separated with spaces)"
        ' (ex.: --run-before "java -jar forge_installer.jar --installClient .")'
        " NOTE: Consider adding --write-profiles argument"
        " NOTE: Consider adding --delete-files forge*installer.jar argument"
        ' NOTE: Will download JRE / JDK 17 if first argument is "java" and replace it with local java path'
        ' NOTE: Will append to the bottom of "run_before" from config file',
    )
    parser.add_argument(
        "--delete-files",
        nargs="+",
        required=False,
        help="delete files before launching minecraft. Uses glob to find files"
        ' (Ex.: --delete-files "forge*installer.jar" "hs_err_pid*.log")',
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


def print_versions(versions: List[Dict]) -> None:
    """Prints local and Mojang versions to console

    Args:
        versions (List[Dict]): result of ProfileParser.parse_versions()
    """
    versions_log = []
    for version in versions:
        versions_log.append(version["id"] + ("*" if version.get("local") else ""))
    logging.info(f"Available versions (* - local): {', '.join(versions_log)}")


def username_dialog() -> str or None:
    """Asks user for username

    Returns:
        str or None: username or None if not provided
    """
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


def check_mml_version() -> None:
    """Checks for latest tag on GitHub and prints it"""
    logging.info("Checking for updates")
    try:
        response = requests.get("https://api.github.com/repos/F33RNI/micro-minecraft-launcher/tags", timeout=TIMEOUT)
        if response.ok:
            tags = json.loads(response.text)
            if len(tags) != 0:
                latest_lag = tags[0]["name"]
                if latest_lag != __version__:
                    new_version_str = f" New version available: {latest_lag} "
                    decorator = "#" * ((80 - len(new_version_str)) // 2)
                    new_version_str = decorator + new_version_str + decorator
                    while len(new_version_str) < 80:
                        new_version_str += "#"
                    logging.warning(new_version_str)
                    logging.warning("# Please download it from:                                                     #")
                    logging.warning("# https://github.com/F33RNI/micro-minecraft-launcher/releases/latest           #")
                    logging.warning("# ############################################################################ #")
        else:
            logging.error(f"Unable to check for updates: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Unable to check for updates: {e}")
        logging.debug("Error details", exc_info=e)


def write_profiles(game_dir: str, versions: List[Dict]) -> None:
    """Writes local version into LAUNCHER_PROFILES_FILE

    Args:
        game_dir (str): path to .minecraft
        versions (List[Dict]): result of ProfileParser.parse_versions()
    """
    launcher_profiles_file_path = os.path.join(game_dir, LAUNCHER_PROFILES_FILE)
    launcher_profiles = {}
    if os.path.exists(launcher_profiles_file_path):
        logging.info(f"Found existing {launcher_profiles_file_path} file. Reading it")
        with open(launcher_profiles_file_path, "r", encoding="utf-8") as launcher_profiles_io:
            launcher_profiles = json.load(launcher_profiles_io)

    profiles = launcher_profiles.get("profiles", {})
    for version in versions:
        if not version.get("local"):
            continue

        version_exists = False
        for _, profile in profiles.items():
            if profile.get("lastVersionId") == version["id"]:
                version_exists = True
                break
        if version_exists:
            logging.debug(f"Not adding {version['id']} to {LAUNCHER_PROFILES_FILE}. Already exists")
            continue

        logging.debug(f"Adding {version['id']} to {LAUNCHER_PROFILES_FILE}")
        profiles[uuid4().hex] = {
            "lastVersionId": version["id"],
            "name": version["id"],
            "type": "custom",
            "icon": LAUNCHER_PROFILES_ICON_DEFAULT,
            "created": version["releaseTime"],
            "lastUsed": version["releaseTime"],
        }

    launcher_profiles["profiles"] = profiles
    launcher_profiles["version"] = launcher_profiles.get("launcher_profiles", 3)
    logging.debug(f"Launcher profiles to write {launcher_profiles}")

    logging.info(f"Writing launcher profiles into {launcher_profiles_file_path}")
    with open(launcher_profiles_file_path, "w+", encoding="utf-8") as launcher_profiles_io:
        json.dump(launcher_profiles, launcher_profiles_io, ensure_ascii=False, indent=4)


def run_before(command: List[str], cwd: str) -> bool:
    """Runs custom command before launching game
    (Will install Java 17 if first argument is "java" and replace it with locally installed java)

    Args:
        command (List[str]): command and all arguments
        cwd (str): path to .minecraft

    Raises:
        Exception: java error or interrupted

    Returns:
        bool: if process finished without interrupting (will not check for process exit code)
    """
    if command[0] == "java":
        java_ = jdk_check_install(version=17)
        if not java_:
            raise Exception("Unable to install Java for --run-before")
        command[0] = java_

    logging.info(f"Running: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        cwd=cwd,
    )

    # Redirect logs and capture CTRL+C
    try:
        while process.poll() is None:
            # Read logs from STOUT (blocking)
            stdout = process.stdout.readline()
            if not stdout:
                continue

            # Redirect log
            log_line = stdout.decode("utf-8", errors="replace").strip()
            logging.info(f"[Run before] {log_line}")

    except (SystemExit, KeyboardInterrupt) as e:
        logging.warning("Interrupted! Killing run-before process")
        if process.poll() is None:
            try:
                process.kill()
            except Exception as e_:
                logging.warning(f"Unable to kill process: {e_}")
                logging.debug("Error details", exc_info=e_)

        # Re-raise interrupt
        raise e

    # Installer stopped
    logging.info("run-before process stopped")
    return True


def delete_files(delete_patterns: List[str]) -> None:
    """Deletes files using glob patterns

    Args:
        delete_patterns (List[str]): patterns for glob.glob
    """
    logging.debug(f"delete_patterns: {' '.join(delete_patterns)}")
    for delete_pattern in delete_patterns:
        for file in glob.glob(delete_pattern):
            logging.debug(f"Found file {file} in pattern {delete_pattern} to delete")
            logging.warning(f"Deleting {file}")
            try:
                if os.path.isdir(file):
                    shutil.rmtree(file, ignore_errors=True)
                    if os.path.exists(file):
                        os.rmdir(file)
                else:
                    os.remove(file)
            except Exception as e:
                logging.error(f"Error deleting {file}: {e}")
                logging.debug("Error details", exc_info=e)


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

    # Fix SSL: CERTIFICATE_VERIFY_FAILED
    cert_file = certifi.where()
    logging.debug(f"SSL certificate file: {cert_file}. Exists? {os.path.exists(cert_file)}")
    os.environ["SSL_CERT_DIR"] = os.path.dirname(cert_file)
    os.environ["SSL_CERT_FILE"] = cert_file
    os.environ["REQUESTS_CA_BUNDLE"] = cert_file

    file_resolver_ = None
    try:
        # Log software version and GitHub link
        logging.info(f"micro-minecraft-launcher version: {__version__}")
        logging.info("https://github.com/F33RNI/micro-minecraft-launcher")

        # Check for updates
        check_mml_version()

        # Detect OS, check and log it
        os_name_ = os_name()
        logging.info(f"Detected OS: {os_name_}")

        config_manager_ = ConfigManager(args.config, args)

        # Log minecraft dir
        game_dir = config_manager_.get("game_dir")
        logging.info(f"Game directory: {game_dir}")
        profile_parser_ = ProfileParser(game_dir)
        versions = profile_parser_.parse_versions()

        # Print available versions and exit
        if args.list_versions:
            print_versions(versions)
            logging_handler_.queue_.put(None)
            return

        # Save found local versions
        if args.write_profiles or config_manager_.get("write_profiles", ignore_args=True):
            write_profiles(game_dir, versions)

        # Run custom command
        run_before_cmd = config_manager_.get("run_before", [], ignore_args=True)
        if args.run_before:
            for run_before_arg in shlex.split(args.run_before, posix=True):
                run_before_cmd.append(run_before_arg)
        logging.info(f"Run before: {' '.join(run_before_cmd)}")
        if run_before_cmd:
            if run_before(run_before_cmd, game_dir):
                # Update profiles
                versions = profile_parser_.parse_versions()
                if args.write_profiles or config_manager_.get("write_profiles"):
                    write_profiles(game_dir, versions)

        # Delete files before launching
        delete_patterns = config_manager_.get("delete_files", [], ignore_args=True)
        if args.delete_files:
            delete_patterns.extend(args.delete_files)
        delete_files(delete_patterns)

        # Check if have anything to launch
        version_id = config_manager_.get("id")
        if version_id:
            logging.info(f"Version ID: {version_id}")

            file_resolver_ = FileResolver(config_manager_.get("resolver_processes"), logging_handler_.queue_)

            username = config_manager_.get("user")
            if not username:
                logging.debug("Asking for username")
                logging_handler_.flush()
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
                file_resolver_,
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

    # Stop all processes
    if file_resolver_ is not None:
        file_resolver_.stop(stop_background_thread=True)

    # Finally, stop logging loop
    logging.info("micro-minecraft-launcher exited")
    logging_handler_.queue_.put(None)


if __name__ == "__main__":

    main()
