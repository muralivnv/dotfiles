import subprocess
import os
import sys
from typing import Optional

DIAGNOSTICS_CMD_FILE = ".ronin/diagnostics.txt"

FZF_CMD = (
    "fzf --tmux bottom,40% --border -i --preview 'bat {1} --highlight-line {2}' --preview-window 'right,+{2}+3/3,~3' "
    "--delimiter @ --nth 1 --scrollbar '▍' --bind=tab:down,shift-tab:up --smart-case --cycle "
    "--style=full:line --layout=reverse --footer 'Error' --bind 'focus:+bg-transform-footer:echo {4} | fold -s -w 100' "
    "--color 'footer-border:#f4a560,footer-label:#ffa07a,footer:#ffa07a' "
)

def get_last_active_tmux_pane() -> Optional[str]:
    try:
        pane = subprocess.check_output(
            ["tmux", "display-message", "-p", "#{pane_id}"],
            universal_newlines=True
        ).strip()
        return pane
    except subprocess.CalledProcessError:
        return None

if __name__ == "__main__":
    if not os.path.exists(DIAGNOSTICS_CMD_FILE):
        exit(1)
    cmds = []
    with open(DIAGNOSTICS_CMD_FILE, "r", encoding="utf8") as infile:
        cmds_ = infile.readlines()
        for cmd in cmds_:
            cmd = cmd.strip()
            if cmd != '':
                cmds.append(cmd)

    # initialize FZF process
    pane_id = get_last_active_tmux_pane()
    if pane_id is None:
        pane_id = "{up-of}"
    fzf_cmd = FZF_CMD + \
        f" --bind \"ctrl-e:execute-silent(tmux send-keys -t '{pane_id}' ':open {{1}}:{{2}}:{{3}}' Enter)\" "
    fzf_proc = subprocess.Popen(fzf_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True, text=True)

    for cmd in cmds:
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        stdout = process.stdout
        if stdout is None:
            print("[ERROR] No stderr stream found — did the command fail to start?", file=sys.stderr)
            continue

        for line in stdout:
            line = line.strip()
            if not line:
                continue
            if fzf_proc.poll() is not None:
                break
            try:
                if fzf_proc.stdin:
                    fzf_proc.stdin.write(line + "\n")
                    fzf_proc.stdin.flush()
            except (BrokenPipeError, AttributeError):
                break
    if fzf_proc.stdin:
        fzf_proc.stdin.close()
    fzf_proc.wait()
