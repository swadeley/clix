# -*- encoding: utf-8 -*-
"""A collection of miscellaneous helpers that don't quite fit in."""
import asyncio
from pathlib import Path
from time import sleep
from uuid import uuid4

import yaml

import asyncssh
from logzero import logger

MODULE_DATA = {}  # not ideal, but async is funky
KEYWORDS = [
    "False",
    "class",
    "finally",
    "is",
    "return",
    "None",
    "continue",
    "for",
    "lambda",
    "try",
    "True",
    "def",
    "from",
    "nonlocal",
    "while",
    "and",
    "del",
    "global",
    "not",
    "with",
    "as",
    "elif",
    "if",
    "or",
    "yield",
    "assert",
    "else",
    "import",
    "pass",
    "break",
    "except",
    "in",
    "raise",
]


def get_cli_list(mock=False):
    """Return a list of saved CLIs, if they exist"""
    cli_dir = Path("CLIs/" if not mock else "tests/CLIs/")
    # check exists
    if not cli_dir.exists():
        return None
    # get all versions in directory, that aren't diffs
    clis = [
        (cli.name, cli.stat().st_mtime) for cli in cli_dir.iterdir() if cli.is_dir()
    ] or []
    clis = [cli for cli, _ in sorted(clis, key=lambda x: x[1], reverse=True)]
    return clis


def get_ver_list(cli_name, mock=False):
    """Return a list of saved CLI versions, if they exist"""
    if mock:
        save_path = Path(f"tests/CLIs/{cli_name}")
    else:
        save_path = Path(f"CLIs/{cli_name}")
    # check exists
    if not save_path.exists():
        return None
    # get all versions in directory, that aren't diffs
    versions = [
        v_file.name.replace(".yaml", "")
        for v_file in save_path.iterdir()
        if "-diff." not in v_file.name
        and "-comp." not in v_file.name
        and ".yaml" in v_file.name
    ] or []
    return sorted(versions, reverse=True)


def get_latest(cli_name=None, mock=False):
    """Get the latest CLI version, if it exists"""
    if not cli_name:
        return get_cli_list(mock=mock)[0]
    else:
        ver_list = get_ver_list(cli_name, mock=mock) or [None]
        return ver_list[0]


def get_previous(cli_name, version, mock=False):
    """Get the CLI version before `version`, if it isn't last"""
    cli_list = get_ver_list(cli_name, mock=mock)
    if version in cli_list:
        v_pos = cli_list.index(version)
        if v_pos + 2 <= len(cli_list):
            return cli_list[v_pos + 1]
    return None


def load_cli(cli_name, version, mock=False):
    """Load the saved yaml to dict, if the file exists"""
    if mock:
        c_path = Path(f"tests/CLIs/{cli_name}/{version}.yaml")
    else:
        c_path = Path(f"CLIs/{cli_name}/{version}.yaml")

    if not c_path.exists():
        logger.warning(f"No file found at {c_path}!")
        return None
    return yaml.load(c_path.open("r")) or None


def shift_text(text, shift):
    """Shifts blocks or a single line of text by 4 * shift spaces"""
    new_text = ""
    if "\n" in text:
        for line in text.split("\n"):
            new_text += "    " * shift + line + "\n"
    else:
        new_text = "    " * shift + text
    return new_text


def clean_keywords(name):
    """If a name matches a python keyword, alter it."""
    if name in KEYWORDS:
        logger.warning(f"Python Keyword Violation! Changing {name} to {name}_")
        name = f"{name}_"
    return name


async def _run_misc_cmd(key, cmd, host, user, pword):
    """Run a single command against a remote host"""
    conn_args = {"host": host, "username": user, "password": pword, "known_hosts": None}
    logger.debug(f"Attempting to run command: {cmd}")
    async with asyncssh.connect(**conn_args) as conn:
        result = await conn.run(cmd, check=False)
        if result.exit_status != 0:
            logger.warning(
                f"""Recieved non-zero exit code: {result.exit_status}
                 for command: {cmd} \n Result: {result.stderr}"""
            )
            result.stdout = None
        MODULE_DATA[key] = result.stdout


def run_misc_cmd(key, cmd, host, user, pword):
    try:
        asyncio.get_event_loop().run_until_complete(
            _run_misc_cmd(key, cmd, host, user, pword)
        )
    except (OSError, asyncssh.Error) as exc:
        logger.warning(f"SSH connection failed: {exc}")
        return False
    return True


def get_max_connections(host, user, pword):
    ses_cmd = "grep MaxSessions /etc/ssh/sshd_config"
    start_cmd = "grep MaxStartups /etc/ssh/sshd_config"
    ses_key = uuid4()
    run_misc_cmd(ses_key, ses_cmd, host, user, pword)
    start_key = uuid4()
    run_misc_cmd(start_key, start_cmd, host, user, pword)
    return MODULE_DATA[ses_key].rstrip(), MODULE_DATA[start_key].rstrip()


def set_max_sessions(init_val, new_val, host, user, pword):
    if isinstance(new_val, int):
        new_val = f"MaxSessions {new_val}"
    sess_cmd = f"sed -i 's/{init_val}/{new_val}/' /etc/ssh/sshd_config"
    if run_misc_cmd(uuid4(), sess_cmd, host, user, pword):
        return new_val
    else:
        return False


def set_max_starts(init_val, new_val, host, user, pword):
    if isinstance(new_val, int):
        new_val = f"MaxStartups {new_val}:30:100"
    start_cmd = f"sed -i 's/{init_val}/{new_val}/' /etc/ssh/sshd_config"
    if run_misc_cmd(uuid4(), start_cmd, host, user, pword):
        return new_val
    else:
        return False


def restart_sshd(host, user, pword):
    restart_key, limit, tries, success = uuid4(), 30, 0, False
    logger.debug("Restarting remote host's sshd")
    run_misc_cmd(restart_key, "systemctl restart sshd", host, user, pword)
    while not success and tries < limit:
        try:
            run_misc_cmd(restart_key, "systemctl status sshd", host, user, pword)
            if "(running)" in MODULE_DATA[restart_key]:
                success = True
            else:
                tries += 1
                sleep(tries)
        except:
            pass
    if success:
        logger.debug("sshd successfully restarted!")
    else:
        logger.warning(
            f"something went wrong while restarting sshd!\n{MODULE_DATA[restart_key]}"
        )
    return success