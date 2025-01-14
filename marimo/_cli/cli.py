# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import click

import marimo._cli.cli_validators as validators
from marimo import __version__, _loggers
from marimo._ast import codegen
from marimo._cli.config.commands import config
from marimo._cli.convert.commands import convert
from marimo._cli.development.commands import development
from marimo._cli.envinfo import get_system_info
from marimo._cli.export.commands import export
from marimo._cli.file_path import validate_name
from marimo._cli.parse_args import parse_args
from marimo._cli.print import red
from marimo._cli.run_docker import (
    prompt_run_in_docker_container,
)
from marimo._cli.upgrade import check_for_updates, print_latest_version
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._server.file_router import AppFileRouter
from marimo._server.model import SessionMode
from marimo._server.start import start
from marimo._server.tokens import AuthToken
from marimo._tutorials import (
    Tutorial,
    create_temp_tutorial_file,
    tutorial_order,
)
from marimo._utils.marimo_path import MarimoPath


def helpful_usage_error(self: Any, file: Any = None) -> None:
    if file is None:
        file = click.get_text_stream("stderr")
    color = None
    click.echo(
        red("Error") + ": %s\n" % self.format_message(),
        file=file,
        color=color,
    )
    if self.ctx is not None:
        color = self.ctx.color
        click.echo(self.ctx.get_help(), file=file, color=color)


click.exceptions.UsageError.show = helpful_usage_error  # type: ignore


def _key_value_bullets(items: list[tuple[str, str]]) -> str:
    max_length = max(len(item[0]) for item in items)
    lines: list[str] = []

    def _sep(desc: str) -> str:
        return ":" if desc else ""

    for key, desc in items:
        # "\b" tells click not to reformat our text
        lines.append("\b")
        lines.append(
            "  * "
            + key
            + _sep(desc)
            + " " * (max_length - len(key) + 2)
            + desc
        )
    return "\n".join(lines)


def _resolve_token(
    token: bool, token_password: Optional[str]
) -> Optional[AuthToken]:
    if token_password:
        return AuthToken(token_password)
    elif token is False:
        # Empty means no auth
        return AuthToken("")
    # None means use the default (generated) token
    return None


main_help_msg = "\n".join(
    [
        "\b",
        "Welcome to marimo!",
        "\b",
        "Getting started:",
        "",
        _key_value_bullets(
            [
                ("marimo tutorial intro", ""),
            ]
        ),
        "\b",
        "",
        "Example usage:",
        "",
        _key_value_bullets(
            [
                (
                    "marimo edit",
                    "create or edit notebooks",
                ),
                (
                    "marimo edit notebook.py",
                    "create or edit a notebook called notebook.py",
                ),
                (
                    "marimo run notebook.py",
                    "run a notebook as a read-only app",
                ),
                (
                    "marimo tutorial --help",
                    "list tutorials",
                ),
            ]
        ),
    ]
)

token_message = (
    "Use a token for authentication. "
    "This enables session-based authentication. "
    "A random token will be generated if --token-password is not set. "
    "If --no-token is set, session-based authentication will not be used. "
)

token_password_message = (
    "Use a specific token for authentication. "
    "This enables session-based authentication. "
    "A random token will be generated if not set. "
)

sandbox_message = (
    "Run the command in an isolated virtual environment using "
    "`uv run --isolated`. Requires `uv`."
)


@click.group(help=main_help_msg)
@click.version_option(version=__version__, message="%(version)s")
@click.option(
    "-l",
    "--log-level",
    default="WARN",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    show_default=True,
    help="Choose logging level.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    default=False,
    show_default=True,
    help="Suppress standard out.",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    show_default=True,
    help="Automatic yes to prompts, running non-interactively.",
)
@click.option(
    "-d",
    "--development-mode",
    is_flag=True,
    default=False,
    show_default=True,
    help="Run in development mode; enables debug logs and server autoreload.",
)
def main(
    log_level: str, quiet: bool, yes: bool, development_mode: bool
) -> None:
    log_level = "DEBUG" if development_mode else log_level
    _loggers.set_level(log_level)

    GLOBAL_SETTINGS.DEVELOPMENT_MODE = development_mode
    GLOBAL_SETTINGS.QUIET = quiet
    GLOBAL_SETTINGS.YES = yes
    GLOBAL_SETTINGS.LOG_LEVEL = _loggers.log_level_string_to_int(log_level)


edit_help_msg = "\n".join(
    [
        "\b",
        "Create or edit notebooks.",
        "",
        _key_value_bullets(
            [
                (
                    "marimo edit",
                    "Start the marimo notebook server",
                ),
                ("marimo edit notebook.py", "Create or edit notebook.py"),
            ]
        ),
    ]
)


@main.command(help=edit_help_msg)
@click.option(
    "-p",
    "--port",
    default=None,
    show_default=True,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    type=str,
    help="Host to attach to.",
)
@click.option(
    "--proxy",
    default=None,
    type=str,
    help="Address of reverse proxy.",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=True,
    show_default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    show_default=True,
    type=str,
    help=token_password_message,
)
@click.option(
    "--base-url",
    default="",
    show_default=True,
    type=str,
    help="Base URL for the server. Should start with a /.",
    callback=validators.base_url,
)
@click.option(
    "--allow-origins",
    default=None,
    multiple=True,
    help="Allowed origins for CORS. Can be repeated. Use * for all origins.",
)
@click.option(
    "--skip-update-check",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't check if a new version of marimo is available for download.",
)
@click.option(
    "--sandbox",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help=sandbox_message,
)
@click.option("--profile-dir", default=None, type=str, hidden=True)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Watch the file for changes and reload the code when saved in another editor.",
)
@click.argument("name", required=False, type=click.Path())
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def edit(
    port: Optional[int],
    host: str,
    proxy: Optional[str],
    headless: bool,
    token: bool,
    token_password: Optional[str],
    base_url: str,
    allow_origins: Optional[tuple[str, ...]],
    skip_update_check: bool,
    sandbox: bool,
    profile_dir: Optional[str],
    watch: bool,
    name: Optional[str],
    args: tuple[str, ...],
) -> None:
    from marimo._cli.sandbox import prompt_run_in_sandbox

    # If file is a url, we prompt to run in docker
    # We only do this for remote files,
    # but later we can make this a CLI flag
    if name is not None and prompt_run_in_docker_container(name):
        from marimo._cli.run_docker import run_in_docker

        run_in_docker(
            name,
            port=port,
            debug=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        )
        return

    if sandbox or prompt_run_in_sandbox(name):
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], name)
        return

    GLOBAL_SETTINGS.PROFILE_DIR = profile_dir
    if not skip_update_check and os.getenv("MARIMO_SKIP_UPDATE_CHECK") != "1":
        GLOBAL_SETTINGS.CHECK_STATUS_UPDATE = True
        # Check for version updates
        check_for_updates(print_latest_version)

    if name is not None:
        # Validate name, or download from URL
        # The second return value is an optional temporary directory. It is
        # unused, but must be kept around because its lifetime on disk is bound
        # to the life of the Python object
        name, _ = validate_name(
            name, allow_new_file=True, allow_directory=True
        )
        is_dir = os.path.isdir(name)
        if os.path.exists(name) and not is_dir:
            # module correctness check - don't start the server
            # if we can't import the module
            codegen.get_app(name)
        elif not is_dir:
            # write empty file
            try:
                with open(name, "w"):
                    pass
            except OSError as e:
                if isinstance(e, FileNotFoundError):
                    # This means that the parent directory does not exist
                    parent_dir = os.path.dirname(name)
                    raise click.ClickException(
                        f"Parent directory does not exist: {parent_dir}"
                    ) from e
                raise
    else:
        name = os.getcwd()

    start(
        file_router=AppFileRouter.infer(name),
        development_mode=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        quiet=GLOBAL_SETTINGS.QUIET,
        host=host,
        port=port,
        proxy=proxy,
        headless=headless,
        mode=SessionMode.EDIT,
        include_code=True,
        watch=watch,
        cli_args=parse_args(args),
        auth_token=_resolve_token(token, token_password),
        base_url=base_url,
        allow_origins=allow_origins,
        redirect_console_to_browser=True,
        ttl_seconds=None,
    )


@main.command(help="Create a new notebook.")
@click.option(
    "-p",
    "--port",
    default=None,
    show_default=True,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    type=str,
    help="Host to attach to.",
)
@click.option(
    "--proxy",
    default=None,
    type=str,
    help="Address of reverse proxy.",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=True,
    show_default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    show_default=True,
    type=str,
    help=token_password_message,
)
@click.option(
    "--base-url",
    default="",
    show_default=True,
    type=str,
    help="Base URL for the server. Should start with a /.",
    callback=validators.base_url,
)
@click.option(
    "--sandbox",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help=sandbox_message,
)
def new(
    port: Optional[int],
    host: str,
    proxy: Optional[str],
    headless: bool,
    token: bool,
    token_password: Optional[str],
    base_url: str,
    sandbox: bool,
) -> None:
    if sandbox:
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], None)
        return

    start(
        file_router=AppFileRouter.new_file(),
        development_mode=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        quiet=GLOBAL_SETTINGS.QUIET,
        host=host,
        port=port,
        proxy=proxy,
        headless=headless,
        mode=SessionMode.EDIT,
        include_code=True,
        watch=False,
        cli_args={},
        auth_token=_resolve_token(token, token_password),
        base_url=base_url,
        redirect_console_to_browser=True,
        ttl_seconds=None,
    )


@main.command(
    help="""Run a notebook as an app in read-only mode.

If NAME is a url, the notebook will be downloaded to a temporary file.

Example:

    marimo run notebook.py
"""
)
@click.option(
    "-p",
    "--port",
    default=None,
    show_default=True,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    type=str,
    help="Host to attach to.",
)
@click.option(
    "--proxy",
    default=None,
    type=str,
    help="Address of reverse proxy.",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=False,
    show_default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    show_default=True,
    type=str,
    help=token_password_message,
)
@click.option(
    "--include-code",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Include notebook code in the app.",
)
@click.option(
    "--session-ttl",
    default=120,
    show_default=True,
    type=int,
    help=("Seconds to wait before closing a session on websocket disconnect."),
)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help=(
        "Watch the file for changes and reload the app. "
        "If watchdog is installed, it will be used to watch the file. "
        "Otherwise, file watcher will poll the file every 1s."
    ),
)
@click.option(
    "--base-url",
    default="",
    show_default=True,
    type=str,
    help="Base URL for the server. Should start with a /.",
    callback=validators.base_url,
)
@click.option(
    "--allow-origins",
    default=None,
    multiple=True,
    help="Allowed origins for CORS. Can be repeated.",
)
@click.option(
    "--redirect-console-to-browser",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Redirect console logs to the browser console.",
)
@click.option(
    "--sandbox",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help=sandbox_message,
)
@click.argument("name", required=True, type=click.Path())
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def run(
    port: Optional[int],
    host: str,
    proxy: Optional[str],
    headless: bool,
    token: bool,
    token_password: Optional[str],
    include_code: bool,
    session_ttl: int,
    watch: bool,
    base_url: str,
    allow_origins: tuple[str, ...],
    redirect_console_to_browser: bool,
    sandbox: bool,
    name: str,
    args: tuple[str, ...],
) -> None:
    from marimo._cli.sandbox import prompt_run_in_sandbox

    # If file is a url, we prompt to run in docker
    # We only do this for remote files,
    # but later we can make this a CLI flag
    if prompt_run_in_docker_container(name):
        from marimo._cli.run_docker import run_in_docker

        run_in_docker(
            name,
            port=port,
            debug=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        )
        return

    if sandbox or prompt_run_in_sandbox(name):
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], name)
        return

    # Validate name, or download from URL
    # The second return value is an optional temporary directory. It is unused,
    # but must be kept around because its lifetime on disk is bound to the life
    # of the Python object
    name, _ = validate_name(name, allow_new_file=False, allow_directory=False)

    # correctness check - don't start the server if we can't import the module
    codegen.get_app(name)

    start(
        file_router=AppFileRouter.from_filename(MarimoPath(name)),
        development_mode=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        quiet=GLOBAL_SETTINGS.QUIET,
        host=host,
        port=port,
        proxy=proxy,
        headless=headless,
        mode=SessionMode.RUN,
        include_code=include_code,
        ttl_seconds=session_ttl,
        watch=watch,
        base_url=base_url,
        allow_origins=allow_origins,
        cli_args=parse_args(args),
        auth_token=_resolve_token(token, token_password),
        redirect_console_to_browser=redirect_console_to_browser,
    )


@main.command(help="Recover a marimo notebook from JSON.")
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def recover(name: str) -> None:
    click.echo(codegen.recover(name))


@main.command(
    help="""Open a tutorial.

marimo is a powerful library for making reactive notebooks
and apps. To get the most out of marimo, get started with a few
tutorials, starting with the intro:

    \b
    marimo tutorial intro

Recommended sequence:

    \b
"""
    + "\n".join(f"    - {name}" for name in tutorial_order)
)
@click.option(
    "-p",
    "--port",
    default=None,
    show_default=True,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    type=str,
    help="Host to attach to.",
)
@click.option(
    "--proxy",
    default=None,
    type=str,
    help="Address of reverse proxy.",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=True,
    show_default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    show_default=True,
    type=str,
    help=token_password_message,
)
@click.argument(
    "name",
    required=True,
    type=click.Choice(tutorial_order),
)
def tutorial(
    port: Optional[int],
    host: str,
    proxy: Optional[str],
    headless: bool,
    token: bool,
    token_password: Optional[str],
    name: Tutorial,
) -> None:
    temp_dir = tempfile.TemporaryDirectory()
    path = create_temp_tutorial_file(name, temp_dir)

    start(
        file_router=AppFileRouter.from_filename(path),
        development_mode=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        quiet=GLOBAL_SETTINGS.QUIET,
        host=host,
        port=port,
        proxy=proxy,
        mode=SessionMode.EDIT,
        include_code=True,
        headless=headless,
        watch=False,
        cli_args={},
        auth_token=_resolve_token(token, token_password),
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )


@main.command()
def env() -> None:
    """Print out environment information for debugging purposes."""
    click.echo(json.dumps(get_system_info(), indent=2))


@main.command(
    help="Install shell completions for marimo. Supports bash, zsh, fish, and elvish."
)
def shell_completion() -> None:
    shell = os.environ.get("SHELL", "")
    if not shell:
        click.echo(
            "Could not determine shell. Please set $SHELL environment variable.",
            err=True,
        )
        return

    shell_name = Path(shell).name

    commands = {
        "bash": (
            'eval "$(_MARIMO_COMPLETE=bash_source marimo)"',
            ".bashrc",
        ),
        "zsh": (
            'eval "$(_MARIMO_COMPLETE=zsh_source marimo)"',
            ".zshrc",
        ),
        "fish": (
            "_MARIMO_COMPLETE=fish_source marimo | source",
            ".config/fish/completions/marimo.fish",
        ),
    }

    if shell_name not in commands:
        supported = ", ".join(commands.keys())
        click.echo(
            f"Unsupported shell: {shell_name}. Supported shells: {supported}",
            err=True,
        )
        return

    cmd, rc_file = commands[shell_name]
    click.secho("Run this command to enable completions:", fg="green")
    click.secho(f"\n    echo '{cmd}' >> ~/{rc_file}\n", fg="yellow")
    click.secho(
        "\nThen restart your shell or run 'source ~/"
        + rc_file
        + "' to enable completions",
        fg="green",
    )


main.command()(convert)
main.add_command(export)
main.add_command(config)
main.add_command(development)
