import unittest
from pathlib import Path

class WorkflowCommandsTest(unittest.TestCase):
    def test_goalie_report_uses_shell_block_not_yaml_folding(self):
        yaml=(Path(__file__).resolve().parents[2]/".github/workflows/nhl-hoy.yml").read_text()
        section=yaml.split("      - name: Integrate goalie observations into pregame evidence",1)[1].split("      - name:",1)[0]
        self.assertIn("        run: |\n",section)
        commands=section.split("        run: |\n",1)[1]
        self.assertIn("          python nhl/goalie_observations.py ",commands)
        self.assertIn('          cat results/nhl/goalie_coverage.md >> "$GITHUB_STEP_SUMMARY"',commands)
        self.assertEqual(commands.count("          cat "),1)

if __name__=="__main__":
    unittest.main()
