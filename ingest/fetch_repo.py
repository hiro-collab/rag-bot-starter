import os
import subprocess
from dotenv import load_dotenv
from pathlib import Path

# Load .env
load_dotenv()

REPO_URL = os.getenv("GIT_REPO_URL")
LOCAL_DIR = Path(os.getenv("LOCAL_REPO_DIR", "./local_repo")).resolve()

def run(cmd: list, cwd=None):
    # Run a shell command and stream output
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=cwd)

def main():
    if not REPO_URL:
        raise SystemExit("GIT_REPO_URL is not set in .env")

    if not LOCAL_DIR.exists():
        # Clone if not exists
        LOCAL_DIR.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", REPO_URL, str(LOCAL_DIR)])
    else:
        # Pull if exists
        run(["git", "fetch", "--all"], cwd=str(LOCAL_DIR))
        run(["git", "pull", "--rebase"], cwd=str(LOCAL_DIR))

    print(f"✅ Repo ready at: {LOCAL_DIR}")

if __name__ == "__main__":
    main()
