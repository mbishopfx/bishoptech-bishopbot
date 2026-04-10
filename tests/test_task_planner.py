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

        self.assertTrue(prompt.startswith("testing"))
        self.assertIn("Suggested execution plan:", prompt)
        self.assertIn("SESSION COMPLETE", prompt)
        self.assertNotIn("Persistent context:", prompt)
        self.assertNotIn("Original user request:", prompt)
        self.assertNotIn("Refined request:", prompt)
        self.assertNotIn("should not appear", prompt)


if __name__ == "__main__":
    unittest.main()
