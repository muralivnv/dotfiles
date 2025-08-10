#!/usr/bin/python3

import subprocess
from argparse import ArgumentParser, Namespace
import os
import datetime
from typing import List
from time import sleep
import logging

logging.basicConfig(format="[%(asctime)s] {%(funcName)s:%(lineno)d} %(levelname)s - %(message)s",
                    datefmt="%d-%b-%y %H:%M:%S")

TEMP_DIR = ".temp"

GITIGNORE = f"""
build/**
install/**
log/**
.helix/**
.vscode/**
.cache/**
.textadept/**
{TEMP_DIR}/**
"""

RSYNC_CMD = ["rsync",
             "--exclude=**/.git",
             "--exclude=**/build",
             "--exclude=**/install",
             "--exclude=**/log",
             "--exclude=**/.helix",
             "--exclude=**/.vscode",
             "--exclude=**/.textadept",
             "--exclude=**/.cache",
             "-azPe"]

################ SYNC HELPER FUNCTIONS
def notify_remote_has_changes():
    os.system("notify-send --urgency=normal \"REMOTE HAS CHANGES\"")

def notify_merge_fail():
    os.system("notify-send --urgency=critical --expire-time=1000 \"REMOTE HAS CHANGES\" \"3-way merge is not successful\" ")

def get_dirty_files(local_dir: str)->list[str]:
    dirty_files = []
    proc = subprocess.Popen(["git", "status", "--porcelain"],
                             stdout=subprocess.PIPE, cwd=local_dir)
    for line in proc.stdout:
        line = line.strip()
        if any(line):
            dirty_file = line[line.find(b' '):]
            dirty_file = dirty_file.decode('utf-8').strip()
            dirty_file = dirty_file.replace('"', '')
            dirty_files.append( dirty_file )
    return dirty_files

def get_remote_file(cli_args: Namespace,
                     file: str) -> None:
    temp_folder = os.path.join(cli_args.local_dir, TEMP_DIR)
    os.makedirs(temp_folder, exist_ok=True)

    file_rel             = os.path.relpath(file, cli_args.dev_sub_dir)
    remote_file_path     = os.path.join(cli_args.remote_dir, file_rel)
    local_temp_file_path = os.path.join(temp_folder, file_rel)

    # Use sshpass and scp to copy files from remote to local TEMP folder
    p = subprocess.Popen(["sshpass", "-p", cli_args.password] + \
                          RSYNC_CMD + ["ssh", f"{cli_args.user_name}@{cli_args.ip_addr}:{remote_file_path}",
                          local_temp_file_path])
    p.wait()

def clean_temp_dir(local_dir: str) -> None:
    os.system(f"rm {os.path.join(local_dir, TEMP_DIR)}/*")

def compute_diff(cli_args: Namespace, file: str) -> List[bool]:
    file_rel = os.path.relpath(file, cli_args.dev_sub_dir)
    remote_file_path = os.path.join(cli_args.local_dir, TEMP_DIR, file_rel)

    proc = subprocess.Popen(["git", "diff", "--exit-code", f"HEAD:{file}", remote_file_path],
                            stdout=subprocess.PIPE, cwd=cli_args.local_dir)
    proc.wait()
    return proc.returncode == 1

def merge_changes_remote_to_local(cli_args: Namespace,
                                  file: str) -> bool:
    local_file_path = os.path.join(cli_args.local_dir, file)

    file_rel = os.path.relpath(file, cli_args.dev_sub_dir)
    remote_file_path = os.path.join(cli_args.local_dir, TEMP_DIR, file_rel)

    # pull base
    base_file = os.path.join(cli_args.local_dir, TEMP_DIR, "base")
    os.system(f"cd {cli_args.local_dir} && git show HEAD:{file} > {base_file}")

    p = subprocess.Popen(["git", "merge-file", local_file_path, base_file, remote_file_path])
    p.wait()

    return p.returncode == 0

def merge_changes_local_to_remote(cli_args: Namespace,
                                  file: str) -> None:
    local_file_path = os.path.join(cli_args.local_dir, file)

    file_rel = os.path.relpath(file, cli_args.dev_sub_dir)
    remote_file_path = os.path.join(cli_args.remote_dir, file_rel)

    # Use sshpass and scp to copy the locally edited file back to the remote server
    p = subprocess.Popen(["sshpass", "-p", cli_args.password] + \
                         [RSYNC_CMD] + ["ssh", local_file_path, f"{cli_args.user_name}@{cli_args.ip_addr}:{remote_file_path}"])
    p.wait()

def git_commit(cli_args: Namespace) -> None:
    p = subprocess.Popen(["git", "add", "*"],
                         cwd=cli_args.local_dir)
    p.wait()

    p = subprocess.Popen(["git", "commit", "-m", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                         cwd=cli_args.local_dir)
    p.wait()

#####################################
def cleanup_fs(cli_args: Namespace)->None:
    os.makedirs(cli_args.local_dir, exist_ok=True)

    # remove .git folder
    if os.path.exists(os.path.join(cli_args.local_dir, ".git")):
        p = subprocess.Popen(["rm", "-rf", ".git"],
                              cwd=cli_args.local_dir)
        p.wait()

    # clean-up local dev folder
    dev_dir = os.path.join(cli_args.local_dir, cli_args.dev_sub_dir)
    if os.path.exists(dev_dir):
        os.system(f"rm -rf {dev_dir}/*")
    else:
        os.makedirs(dev_dir)

def init_git_system(cli_args: Namespace)->None:
    p = subprocess.Popen(["git", "init"],
                         cwd=cli_args.local_dir)
    p.wait()

    with open(os.path.join(cli_args.local_dir, ".gitignore"), "w",
              encoding="utf-8") as out:
        out.write(GITIGNORE)

    p = subprocess.Popen(["git", "add", "*"],
                         cwd=cli_args.local_dir)
    p.wait()

    p = subprocess.Popen(["git", "commit", "-m", "Initial Commit"],
                         cwd=cli_args.local_dir)
    p.wait()

def pull_remote_files(cli_args: Namespace, silent:bool=False)->None:
    p = subprocess.Popen(["sshpass", "-p", cli_args.password] + \
                          RSYNC_CMD + ["--quite"] if silent else [] +
                          ["ssh",
                          f"{cli_args.user_name}@{cli_args.ip_addr}:{cli_args.remote_dir}",
                          os.path.join(cli_args.local_dir, cli_args.dev_sub_dir)])
    p.wait()

def create_tmux_session(cli_args: Namespace)->str:
    prefix = f"{cli_args.user_name}@{cli_args.ip_addr}_"
    prefix = prefix.replace(".", "_")
    try:
        output = subprocess.check_output(["tmux", "list-sessions", "-F", "#{session_name}"])
        existing_sessions = output.decode("utf-8").split("\n")
    except subprocess.CalledProcessError:
        return f"{prefix}0"

    matching_sessions = [session[len(prefix):] for session in existing_sessions if session.startswith(prefix)]
    counts = [int(session.split("_")[-1]) for session in matching_sessions]
    count = max(counts, default=0)
    return f"{prefix}{count+1}"

def launch_editor_tmux(cli_args: Namespace)->None:
    session_name = create_tmux_session(cli_args)
    os.system(f"x-terminal-emulator -e tmux new -s {session_name} &")
    sleep(0.8) # for tmux session to register
    os.system(f"tmux send-keys -t '{session_name}' 'cd {cli_args.local_dir} && ${{EDITOR}} {cli_args.local_dir}' Enter")

def launch_editor_non_tmux(cli_args: Namespace)->None:
    basename = os.path.basename(cli_args.remote_dir)
    os.system(f"x-terminal-emulator -T \"{cli_args.user_name}@{cli_args.ip_addr}:{basename}\"-e ${{EDITOR}} {cli_args.local_dir} &")

def launch_editor(cli_args: Namespace)->None:
    if cli_args.launch_editor:
        if cli_args.tmux:
            launch_editor_tmux(cli_args)
        else:
            launch_editor_non_tmux(cli_args)

def commit(cli_args: Namespace)->None:
    files = get_dirty_files(cli_args.local_dir)
    if any(files):
        logging.info("local-dir is DIRTY, syncing to remote")
        notify = False
        for file in files:
            get_remote_file(cli_args, file)
            is_file_changed_remote = compute_diff(cli_args,
                                                  file)
            notify |= is_file_changed_remote
            if is_file_changed_remote:
                logging.warning("remote has changes for file -- %s", file)
                logging.warning("performing 3-way merge for file -- %s", file)
                is_success = merge_changes_remote_to_local(cli_args,
                                                           file)
                if not is_success:
                    logging.warning("3-way merge is not successful for file -- %s", file)
                    notify_merge_fail()
                clean_temp_dir(cli_args.local_dir)

            logging.info("syncing local changes to remote for file -- %s", file)
            merge_changes_local_to_remote(cli_args, file)
        git_commit(cli_args)
        if notify:
            logging.warning("remote has changes and has been merged into local")
            notify_remote_has_changes()

    # if remote has other changes
    pull_remote_files(cli_args, silent=True)
    files = get_dirty_files(cli_args.local_dir)
    if any(files):
        logging.warning("remote has some other changes for following files")
        for i, file in enumerate(files):
            logging.warning(" [%d] : %s", i, file)

        logging.info("committing remote changes")
        git_commit(cli_args)

def periodic_commit(cli_args: Namespace) -> None:
    while(True):
        commit(cli_args)
        sleep(cli_args.commit_every)

def setup_cli_args()->ArgumentParser:
    cli = ArgumentParser()
    cli.add_argument("--username"  , "-u",  type=str, dest="user_name",  required=True)
    cli.add_argument("--ip",                type=str, dest="ip_addr",    required=True)
    cli.add_argument("--password"  , "-p",  type=str, dest="password",   required=True)
    cli.add_argument("--remote-dir", "-r",  type=str, dest="remote_dir", required=True)
    cli.add_argument("--local-dir" , "-l",  type=str, dest="local_dir",  required=False, default=os.getcwd())

    cli.add_argument("--dev-sub-dir", "-d", type=str, dest="dev_sub_dir", required=False, default="src",
                     help="this is the sub-directory where source will be pulled")

    cli.add_argument("--commit-every-sec",  type=float, default=5.0, dest="commit_every", required=False)
    cli.add_argument("--no-editor", action="store_false", default=True, dest="launch_editor")
    cli.add_argument("--no-tmux", action="store_false", default=True, dest="tmux")
    return cli

def parse_args(cli_args: ArgumentParser) -> Namespace:
    parsed_args, _ = cli_args.parse_known_args()
    if not parsed_args.remote_dir.endswith("/"):
        parsed_args.remote_dir = parsed_args.remote_dir + "/"
    return parsed_args

if __name__ == "__main__":
    cli = setup_cli_args()
    parsed_args = parse_args(cli)

    logging.info("cleaning path -- %s", parsed_args.local_dir)
    cleanup_fs(parsed_args)

    logging.info("pulling remote %s@%s:%s",
                 parsed_args.user_name, parsed_args.ip_addr, parsed_args.remote_dir)
    pull_remote_files(parsed_args)

    logging.info("performing initial commit")
    init_git_system(parsed_args)
    launch_editor(parsed_args)

    try:
        periodic_commit(parsed_args)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(e)
    finally:
        commit(parsed_args)
