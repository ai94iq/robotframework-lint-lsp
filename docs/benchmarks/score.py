"""Score every run: cost, tries, time from the transcript; quality from dryrun and robocop."""
import glob
import json
import os
import re
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / ".venv"
VENV = ROOT / "Scripts" if (ROOT / "Scripts").is_dir() else ROOT / "bin"
# Agent-written suites run here: no inherited secrets or tokens, and a hung suite cannot stall scoring.
SUITE_ENV = {k: v for k in ("SYSTEMROOT", "PATH", "TEMP", "TMP") if (v := os.environ.get(k))}
SUITE_TIMEOUT_S = 300


def transcript(path: Path) -> dict:
    tools, result = Counter(), {}
    for line in path.open(encoding="utf-8"):
        msg = json.loads(line)
        if msg.get("type") == "assistant":
            for block in msg["message"].get("content", []):
                if block.get("type") == "tool_use":
                    name = block["name"]
                    if name == "Bash" and "robot " in json.dumps(block["input"]):
                        name = "robot_runs"
                    tools["mcp" if name.startswith("mcp__") else name] += 1
        if msg.get("type") == "result":
            result = msg
    return {"cost": result.get("total_cost_usd", 0), "turns": result.get("num_turns", 0),
            "seconds": result.get("duration_ms", 0) / 1000, "edits": tools["Edit"] + tools["Write"],
            "robot_runs": tools["robot_runs"], "mcp_calls": tools["mcp"]}


REPO = VENV.parent.parent
SUITES = ["calculator.robot", "sorter.robot"]


def robot(folder: Path, *flags: str) -> tuple[int, int]:
    """Run both suites; return (passed, failed). A missing or broken suite counts as failed."""
    present = [s for s in SUITES if (folder / s).exists()]
    if not present:
        return 0, 1
    try:
        subprocess.run([str(VENV / "robot"), *flags, "--output", "out.xml", "--report", "NONE", "--log", "NONE",
                               "--console", "none", *present], cwd=folder, capture_output=True, text=True,
                       env=SUITE_ENV, timeout=SUITE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return 0, 1
    stats = re.search(r'<stat pass="(\d+)" fail="(\d+)" skip="\d+">All Tests</stat>',
                      (folder / "out.xml").read_text(encoding="utf-8")) if (folder / "out.xml").exists() else None
    (folder / "out.xml").unlink(missing_ok=True)
    if not stats:
        return 0, 1
    passed, failed = int(stats[1]), int(stats[2])
    return passed, failed + (len(SUITES) - len(present))


def issues(folder: Path) -> int:
    files = [str(p.resolve()) for p in folder.glob("*.r*") if p.suffix in (".robot", ".resource")]
    if not files:
        return 99
    out = subprocess.run([str(VENV / "robocop"), "check", *files], cwd=REPO, capture_output=True, text=True)
    out = out.stdout + out.stderr
    found = re.search(r"Found (\d+) issue", out)
    return int(found[1]) if found else (0 if "No issues" in out else 99)


def quality(suite: Path) -> dict:
    folder = suite.parent
    dry_pass, dry_fail = robot(folder, "--dryrun")
    run_pass, run_fail = robot(folder)
    return {"dryrun_fail": dry_fail, "run_pass": run_pass, "run_fail": run_fail,
            "all_green": int(run_fail == 0 and run_pass > 0), "lint_issues": issues(folder)}


def summarize(arm: str, rows: list[dict]) -> None:
    keys = rows[0].keys()
    print(f"\n{arm} (n={len(rows)})")
    for key in keys:
        values = [r[key] for r in rows]
        print(f"  {key:13} mean {statistics.mean(values):8.4g}  median {statistics.median(values):8.4g}  sum {sum(values):8.4g}")


root = Path(sys.argv[1])
for arm in ("lint", "mcp", "nolint"):
    rows = []
    for path in sorted(root.glob(f"{arm}_*.jsonl")):
        rows.append({**transcript(path), **quality(path.with_suffix("") / "suite.robot")})
    if rows:
        summarize(arm, rows)
