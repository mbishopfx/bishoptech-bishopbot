import unittest

from services.ops_phase import DEFAULT_OPS_PHASE, make_ops_phase_state, render_ops_phase_block, render_ops_protocol_block


class OpsPhaseTests(unittest.TestCase):
    def test_render_ops_protocol_block_is_concise_and_actionable(self):
        block = render_ops_protocol_block()
        self.assertIn("## Bishop ops protocol", block)
        self.assertIn("- plan briefly, then execute in an isolated terminal", block)
        self.assertIn("- verify the result against the request", block)

    def test_render_ops_phase_block_defaults_to_execute(self):
        block = render_ops_phase_block(DEFAULT_OPS_PHASE, reason="runtime prompt composition")
        self.assertIn("## Ops phase", block)
        self.assertIn("- phase: execute", block)
        self.assertIn("- next: verify", block)
        self.assertIn("use tools now", block.lower())

    def test_make_ops_phase_state_uses_reasonable_defaults(self):
        state = make_ops_phase_state("recover", reason="debugging a failure")
        self.assertEqual(state.phase, "recover")
        self.assertEqual(state.next_expected, "verify")
        self.assertTrue(state.needs_verification)
        self.assertIn("operator", state.tags)


if __name__ == "__main__":
    unittest.main()
