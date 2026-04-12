import unittest

from services.task_planner import TaskPlanner


class TaskPlannerTests(unittest.TestCase):
    def test_build_cli_prompt_for_gemini_is_compact_and_uses_original_request(self):
        prompt = TaskPlanner.build_cli_prompt(
            "Run a test command.",
            ["Run the requested test command"],
            mode="gemini",
            context_block="should not appear",
            original_request="testing",
        )

        self.assertIn("Follow the project guidance in `GEMINI.md`", prompt)
        self.assertIn("## Ops phase", prompt)
        self.assertIn("- phase: execute", prompt)
        self.assertTrue(prompt.endswith('Keep updates brief. When the task is fully complete, print "SESSION COMPLETE" on its own line followed by a short final summary.'))
        self.assertIn("testing", prompt)
        self.assertIn("Suggested execution plan:", prompt)
        self.assertIn("SESSION COMPLETE", prompt)
        self.assertNotIn("Persistent context:", prompt)
        self.assertNotIn("Original user request:", prompt)
        self.assertNotIn("Refined request:", prompt)
        self.assertNotIn("should not appear", prompt)


if __name__ == "__main__":
    unittest.main()
