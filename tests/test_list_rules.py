"""robocop list rules has no --custom-rules flag; a config file lists the RFL rules."""

import subprocess
import sys


def test_config_lists_all_rfl_rules(tmp_path):
    config = tmp_path / "robocop.toml"
    config.write_text('[tool.robocop.lint]\ncustom_rules = ["robotframework_lint"]\n', encoding="utf-8")
    result = subprocess.run([sys.executable, "-I", "-m", "robocop", "list", "rules", "--config", str(config)],
                            capture_output=True, text=True, check=False, cwd=tmp_path)
    for n in range(1, 7):
        assert f"RFL00{n} [W]" in result.stdout
    assert "RFL007 [E]" in result.stdout
