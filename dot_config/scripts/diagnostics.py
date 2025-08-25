import subprocess
import os

DIAGNOSTICS_CMD_FILE = ".ronin/diagnostics.txt"

if __name__ == "__main__":
    if not os.path.exists(DIAGNOSTICS_CMD_FILE):
        exit(1)
    with open(DIAGNOSTICS_CMD_FILE, "r", encoding="utf8") as infile:
        cmd = infile.read().strip()
    result = subprocess.run(cmd, shell=True)   
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
