#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["watchfiles", "rich"]
# ///

import subprocess
import argparse
import os
import logging
from watchfiles import watch, DefaultFilter, Change
from rich.logging import RichHandler
from rich.console import Console

# Setup Rich console and logging
console = Console()
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(markup=True, rich_tracebacks=True, show_path=False)]
)
log = logging.getLogger("sync")

# Base rsync arguments
BASE_RSYNC_CMD = [
    "rsync",
    # Tells rsync to respect .gitignore files automatically!
    "--filter=:- .gitignore",
    "--exclude=**/.git",
    "--exclude=**/.helix",
    "--exclude=**/.vscode",
    "--exclude=**/.cache",
    "-azP"
]

WATCH_ARGS = {
    "debounce": 500,
    "step": 100,
    "watch_filter": DefaultFilter(
        ignore_dirs=(
            "__pycache__", "build", ".git", ".hg", ".svn", ".tox",
            ".venv", ".idea", "node_modules", ".mypy_cache", ".pytest_cache",
            "install", "log", "dist", "target"
        ),
        ignore_entity_patterns=(
            "\\.py[cod]$", "\\.___jb_...___$", "\\.sw.$", "~$",
            "^\\.\\#", "^\\.DS_Store$", "^flycheck_", "\\.bck$"
        )
    )
}

def get_ssh_mux_args(cli_args: argparse.Namespace) -> list[str]:
    """Generate multiplexing args keyed to the specific user/host/port combo."""
    socket_path = f"/tmp/ssh_sync_mux_{cli_args.user_name}@{cli_args.ip_addr}_{cli_args.port}"
    return [
        "-o", "ControlMaster=auto",
        "-o", f"ControlPath={socket_path}",
        "-o", "ControlPersist=10m"
    ]

def get_ssh_base_cmd(cli_args: argparse.Namespace) -> list[str]:
    """Build the base SSH command with isolated connection reuse and custom port."""
    cmd = ["ssh", "-p", str(cli_args.port)] + get_ssh_mux_args(cli_args)
    if cli_args.identity:
        cmd.extend(["-i", cli_args.identity])
    return cmd

def get_rsync_base_cmd(cli_args: argparse.Namespace) -> list[str]:
    """Build the rsync command with embedded SSH multiplexing options."""
    mux_str = " ".join(get_ssh_mux_args(cli_args))
    ssh_transport = f"ssh -p {cli_args.port} {mux_str}"
    if cli_args.identity:
        ssh_transport += f" -i '{cli_args.identity}'"
    return BASE_RSYNC_CMD + ["-e", ssh_transport]

def initial_sync(cli_args: argparse.Namespace) -> None:
    """Handle the startup sync direction."""
    if cli_args.init == "skip":
        log.info("Skipping initial sync as requested.")
        return

    cmd = get_rsync_base_cmd(cli_args)
    
    if cli_args.init == "pull":
        log.info(f"Pulling from [bold cyan]{cli_args.user_name}@{cli_args.ip_addr}:{cli_args.remote_dir}[/]")
        cmd += [f"{cli_args.user_name}@{cli_args.ip_addr}:{cli_args.remote_dir}", "."]
    elif cli_args.init == "push":
        log.info(f"Pushing to [bold cyan]{cli_args.user_name}@{cli_args.ip_addr}:{cli_args.remote_dir}[/]")
        cmd += [".", f"{cli_args.user_name}@{cli_args.ip_addr}:{cli_args.remote_dir}"]

    result = subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        log.error(f"[red]Initial sync failed:[/] {result.stderr}")
        exit(1)

def push_files_bulk(cli_args: argparse.Namespace, local_file_paths: list[str]) -> None:
    """Push multiple files in a single rsync transaction to prevent subprocess bottlenecks."""
    # Convert absolute paths to relative paths based on current directory
    rel_paths = [os.path.relpath(p, os.getcwd()) for p in local_file_paths]
    
    log.info(f"[green]Pushing {len(rel_paths)} file(s)[/]")
    for p in rel_paths[:3]: # Log up to 3 files to avoid terminal spam
        log.info(f"  -> {p}")
    if len(rel_paths) > 3:
        log.info(f"  ... and {len(rel_paths) - 3} more")

    # The -R (--relative) flag tells rsync to create the necessary parent 
    # directories on the remote side automatically matching the local relative path.
    cmd = get_rsync_base_cmd(cli_args) + ["-R"] + rel_paths + [
        f"{cli_args.user_name}@{cli_args.ip_addr}:{cli_args.remote_dir}"
    ]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def delete_remote(cli_args: argparse.Namespace, local_file_path: str) -> None:
    """Delete a file/folder on the remote server if it was removed locally."""
    rel_path = os.path.relpath(local_file_path, os.getcwd())
    remote_path = os.path.join(cli_args.remote_dir, rel_path)

    log.info(f"[red]Deleting[/] {rel_path}")
    
    cmd = get_ssh_base_cmd(cli_args) + [
        f"{cli_args.user_name}@{cli_args.ip_addr}",
        f"rm -rf '{remote_path}'"
    ]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def run_watch_loop(cli_args: argparse.Namespace) -> None:
    """Watch the local directory and batch sync changes."""
    watch_path = os.getcwd()
    
    console.print("\n[bold green]✅ Synced and ready to edit![/]")
    console.print(f"[dim]Watching for changes in: {watch_path}[/dim]\n")

    for changes in watch(watch_path, **WATCH_ARGS):
        files_to_push = []
        
        for change, file_path in changes:
            if change == Change.deleted:
                delete_remote(cli_args, file_path)
            else:
                files_to_push.append(file_path)
                
        # Batch push all modified/added files in one network call
        if files_to_push:
            push_files_bulk(cli_args, files_to_push)

def close_mux_connection(cli_args: argparse.Namespace) -> None:
    """Gracefully close the background SSH multiplexing master connection."""
    cmd = get_ssh_base_cmd(cli_args) + ["-O", "exit", f"{cli_args.user_name}@{cli_args.ip_addr}"]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def setup_cli_args() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Live secure remote file syncer")
    cli.add_argument("--username", "-u", type=str, dest="user_name", required=True)
    cli.add_argument("--ip", type=str, dest="ip_addr", required=True)
    cli.add_argument("--remote-dir", "-r", type=str, dest="remote_dir", required=True)
    cli.add_argument("--port", "-p", type=int, dest="port", required=False, default=22,
                     help="Custom SSH port (default: 22)")
    cli.add_argument("--identity", "-i", type=str, dest="identity", required=False,
                     help="Path to SSH private key (e.g., ~/.ssh/id_ed25519)")
    cli.add_argument("--init", choices=["pull", "push", "skip"], default="pull",
                     help="Initial sync behavior (default: pull)")
    return cli

def parse_args(cli: argparse.ArgumentParser) -> argparse.Namespace:
    parsed_args, _ = cli.parse_known_args()
    if not parsed_args.remote_dir.endswith("/"):
        parsed_args.remote_dir = parsed_args.remote_dir + "/"
        
    if parsed_args.identity:
        parsed_args.identity = os.path.expanduser(parsed_args.identity)
        if not os.path.exists(parsed_args.identity):
            console.print(f"[bold red]Error:[/] Identity file '{parsed_args.identity}' not found.")
            exit(1)
            
    return parsed_args

if __name__ == "__main__":
    cli = setup_cli_args()
    parsed_args = parse_args(cli)

    initial_sync(parsed_args)

    try:
        run_watch_loop(parsed_args)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Exiting gracefully...[/]")
    except Exception as e:
        log.error(f"[bold red]Fatal exception:[/bold red] {e}")
    finally:
        # Ensures the SSH connection doesn't hang open in the background indefinitely
        close_mux_connection(parsed_args)
