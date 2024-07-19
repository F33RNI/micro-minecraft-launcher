# 🧱 micro-minecraft-launcher

## Simple cross-platform cli launcher for Minecraft

### 📦 Highly configurable and ideal for your modpacks

----------

<div style="width:100%;text-align:center;">
    <p align="center">
        <img src="https://badges.frapsoft.com/os/v1/open-source.png?v=103" >
        <img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/F33RNI/micro-minecraft-launcher/tests.yml">
        <img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/F33RNI/micro-minecraft-launcher/release.yml">
        <img alt="GitHub License" src="https://img.shields.io/github/license/F33RNI/micro-minecraft-launcher">
    </p>
</div>

----------

## 😋 Support Project

> 💜 Please support the project

- BTC: `bc1qaj2ef2jlrt2uafn4kc9cmscuu8yqkjkvxxr5zu`
- ETH: `0x284E6121362ea1C69528eDEdc309fC8b90fA5578`
- ZEC: `t1Jb5tH61zcSTy2QyfsxftUEWHikdSYpPoz`

- Or by my music on [🔷 bandcamp](https://f3rni.bandcamp.com/)

- Or [message me](https://t.me/f33rni) if you would like to donate in other way 💰

----------

## ⚠️ Disclaimer

> micro-minecraft-launcher is under development. Serious bugs are possible!
>
> ⚠️ Not tested on OSX

----------

## ❓ Getting Started

### 📄 CLI usage

```text
usage: micro-minecraft-launcher-1.2.dev-linux-x86_64 [-h] [-c CONFIG] [-d GAME_DIR] [-l] [-u USER] [--auth-uuid AUTH_UUID]
                                                     [--auth-access-token AUTH_ACCESS_TOKEN] [--user-type USER_TYPE] [-i]
                                                     [--java-path JAVA_PATH] [-e KEY=VALUE [KEY=VALUE ...]] [-j JVM_ARGS]
                                                     [-g GAME_ARGS] [--resolver-processes RESOLVER_PROCESSES] [--write-profiles]
                                                     [--run-before RUN_BEFORE [RUN_BEFORE ...]]
                                                     [--delete-files DELETE_FILES [DELETE_FILES ...]] [--verbose] [--version]
                                                     [id]

Simple cross-platform cli launcher for Minecraft

positional arguments:
  id                    minecraft version to launch. Run with --list-versions to see available versions

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        path to config file (Default: .micro-minecraft-launcher.json)
  -d GAME_DIR, --game-dir GAME_DIR
                        path to .minecraft (Default: /home/fern/.minecraft)
  -l, --list-versions   print online (official), local versions and exit
  -u USER, --user USER  player's username
  --auth-uuid AUTH_UUID
                        player's UUID (Default: offline UUID from username)
  --auth-access-token AUTH_ACCESS_TOKEN
                        Mojang Access Token or the final token in the Microsoft authentication scheme
  --user-type USER_TYPE
                        "msa" for Microsoft Authentication Scheme, "legacy" for Legacy Minecraft Authentication and "mojang" for
                        Legacy Mojang Authentication (Default: mojang)
  -i, --isolate         put "saves", "logs" and all other profile data inside versions/version_id directory instead of game_dir
  --java-path JAVA_PATH
                        custom path to java binary (Default: download locally)
  -e KEY=VALUE [KEY=VALUE ...], --env-variables KEY=VALUE [KEY=VALUE ...]
                        env variable(s) for final command as key=value pairs (Ex.: -e version_type=snapshot launcher_name=custom-
                        launcher) NOTE: If a value contains spaces, you should define it with double quotes: launcher_name="Custom
                        launcher" NOTE: Values are always treated as strings NOTE: Will merge "env_variables" from config file and
                        overwrite same variables
  -j JVM_ARGS, --jvm-args JVM_ARGS
                        extra arguments for Java separated with spaces (Ex.: -j="-Xmx6G -XX:G1NewSizePercent=20") NOTE: You should
                        define it with double quotes as in example NOTE: If an argument contains spaces, you should define it with
                        double quotes: -j '-foo "multiple words"' NOTE: Will append to the bottom of "game_args" from config file
  -g GAME_ARGS, --game-args GAME_ARGS
                        extra arguments for Minecraft separated with spaces (Ex.: -g="--server 192.168.0.1 --port 25565") NOTE: You
                        should define it with double quotes as in example NOTE: If an argument contains spaces, you should define it
                        with double quotes: -g '-foo "multiple words"' NOTE: Will append to the bottom of "game_args" from config
                        file
  --resolver-processes RESOLVER_PROCESSES
                        number of processes to resolve (download, copy and unpack) files(Default: 4)
  --write-profiles      write all found local versions into game_dir/launcher_profiles.json (useful for installing Forge/Fabric)
  --run-before RUN_BEFORE [RUN_BEFORE ...]
                        run specified command before launching game (ex.: --run-before java -jar forge_installer.jar --installClient
                        .) NOTE: Consider adding --write-profiles argument NOTE: Consider adding --delete-files forge*installer.jar
                        argument NOTE: Will download JRE / JDK 17 if first argument is "java" and replace it with local java path
  --delete-files DELETE_FILES [DELETE_FILES ...]
                        delete files before launching minecraft. Uses glob to find files (Ex.: --delete-files "forge*installer.jar"
                        "hs_err_pid*.log")
  --verbose             debug logs
  --version             show launcher's version number and exit

examples:
  micro-minecraft-launcher --list-versions
  micro-minecraft-launcher 1.21
  micro-minecraft-launcher --isolate 1.18.2
  micro-minecraft-launcher --config /path/to/custom/micro-minecraft-launcher.json
  micro-minecraft-launcher -d /path/to/custom/minecraft -j="-Xmx6G" -g="--server 192.168.0.1" 1.21
  micro-minecraft-launcher -j="-Xmx4G" -g="--width 800 --height 640" 1.18.2
  micro-minecraft-launcher --write-profiles
  micro-minecraft-launcher --write-profiles --run-before java -jar forge-1.18.2-40.2.4-installer.jar --delete-files forge*.jar
```

> ⚠️ NOTE: CLI arguments will overwrite config

### 📦 Use in modpacks

> You can use micro-minecraft-launcher in your modpack. For that, create configuration file (see section below)
> and install custom profile (`versions/version_id/version_id.json`) and it's extra libraries if needed (ex. forge)

- To download executable file, go to the
  link <https://github.com/F33RNI/micro-minecraft-launcher/releases/latest> and download the file for your device
- Alternatively, you can build the app yourself. For this, refer to the `🏗️ Build from Source` section

### ⚙️ Config file

> With configuration file, users can just lauch executable file without any other arguments
> For that, create file named `.micro-minecraft-launcher.json` in the same directory as launcher and specify whatever
> you want in it

```text
{
  "game_dir": "path/to/custom/game/dir or . to use current dir",
  "id": "version id to launch. Ex.: 1.18.2-forge-40.2.4",
  "isolate_profile": true to save logs, opions, saves, resourcepacks, etc. inside versions/version_id,
  "user": "player's username (if not specified, user will be asked)",
  "auth_uuid": "player's UUID",
  "auth_access_token": "Mojang Access Token or the final token in the Microsoft authentication scheme",
  "user_type":  "msa" for Microsoft Authentication Scheme,
                "legacy" for Legacy Minecraft Authentication and
                "mojang" for Legacy Mojang Authentication (Default: mojang),
  "java_path": "path/to/custom/java/executable",
  "env_variables": {
    "launcher_name": "custom-launcher"
  }
  "jvm_args": [
    "-Xss1M",
    "-Xmx4G",
    "-XX:+UnlockExperimentalVMOptions",
    "-XX:+UseG1GC",
    "-XX:G1NewSizePercent=20",
    "-XX:G1ReservePercent=20",
    "-XX:MaxGCPauseMillis=50",
    "-XX:G1HeapRegionSize=32M",
    "-Dfml.ignoreInvalidMinecraftCertificates=true",
    "-Dfml.ignorePatchDiscrepancies=true",
    "-Djava.net.preferIPv4Stack=true",
    "-Dminecraft.applet.TargetDirectory=."
  ],
  "game_args": [
    "--server",
    "server ip to join automatically",
    "--width",
    "925",
    "--height",
    "530"
  ],
  "resolver_processes": 4 (number of processes to download / copy / unpack files),
  "write_profiles": true (write all found local versions into game_dir/launcher_profiles.json),
  "run_before": [
    "java",
    "-jar",
    "path/to/forge-...-installer.jar",
    "--installClient",
    "."
  ]
  "delete_files": [
      "any file patterns to delete (for glob)",
      ...
  ]
}
```

> NOTE: You can omit any config key. None of them are required

#### Example config file

```json
{
    "game_dir": ".",
    "id": "1.18.2-forge-40.2.4",
    "jvm_args": [
        "-Xss1M",
        "-Xmx4G",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+UseG1GC",
        "-XX:G1NewSizePercent=20",
        "-XX:G1ReservePercent=20",
        "-XX:MaxGCPauseMillis=50",
        "-XX:G1HeapRegionSize=32M",
        "-Dfml.ignoreInvalidMinecraftCertificates=true",
        "-Dfml.ignorePatchDiscrepancies=true",
        "-Djava.net.preferIPv4Stack=true",
        "-Dminecraft.applet.TargetDirectory=."
    ],
    "game_args": [
        "--width",
        "925",
        "--height",
        "530"
    ],
    "write_profiles": true,
    "run_before": [
        "java",
        "-jar",
        "forge-1.18.2-40.2.4-installer.jar",
        "--installClient",
        "."
    ],
    "delete_files": [
        "forge-1.18.2-40.2.4-installer*",
        "hs_err_pid*.log"
    ]
}
```

----------

## 🏗️ Build from Source

- Install Python (tested on **3.11** and **3.12**)
- Clone repo

    ```shell
    git clone https://github.com/F33RNI/micro-minecraft-launcher
    cd micro-minecraft-launcher
    ```

- Create virtual environment and install dependencies

    ```shell
    python -m venv venv

    # For Linux
    source venv/bin/activate

    # For Windows
    venv\Scripts\activate.bat

    pip install -r requirements.txt --upgrade
    ```

- **Launch** micro-minecraft-launcher

    ```shell
    python main.py --verbose
    ```

- **Build** using PyInstaller

    ```shell
    pip install pyinstaller
    pyinstaller main.spec

    # Executable will be inside dist/ directory
    ```

----------

## ✨ Contribution

- Anyone can contribute! Just create a **pull request**
- Please use black formatter style for code
- Please use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#specification>) style for commits
