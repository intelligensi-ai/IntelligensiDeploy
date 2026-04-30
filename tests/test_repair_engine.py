import unittest

from intelligensi_deploy.agent.repair_engine import classify_failure, resolve_repair_action


class RepairEngineTests(unittest.TestCase):
    def test_capacity_failure_is_safe_and_retryable(self):
        classification = classify_failure(
            ["Lambda API error 400: insufficient-capacity not enough capacity"]
        )
        self.assertEqual(classification.category, "lambda_capacity")
        self.assertTrue(classification.safe_to_auto_apply)
        action = resolve_repair_action(classification, retry_number=0, retry_limit=3)
        self.assertEqual(action.id, "retry_next_lambda_gpu")
        self.assertTrue(action.retry_allowed)

    def test_credentials_are_manual_only(self):
        classification = classify_failure(["Lambda API error 401 invalid-api-key"])
        self.assertEqual(classification.category, "credentials")
        self.assertFalse(classification.safe_to_auto_apply)
        action = resolve_repair_action(classification, retry_number=0, retry_limit=3)
        self.assertEqual(action.risk_level, "manual")
        self.assertTrue(action.requires_operator_secret)

    def test_ssh_readiness_is_bounded(self):
        classification = classify_failure(["ssh: connection timed out"])
        action = resolve_repair_action(classification, retry_number=6, retry_limit=6)
        self.assertEqual(classification.category, "ssh_readiness")
        self.assertFalse(action.retry_allowed)
        self.assertEqual(action.command_or_patch, "retry-limit-reached")

    def test_unknown_failure_requires_review(self):
        classification = classify_failure(["unexpected provider response"])
        self.assertEqual(classification.category, "unknown")
        self.assertFalse(classification.retry_allowed)

    def test_ltx_missing_env_file_suggests_bootstrap(self):
        classification = classify_failure(
            [
                "[Deploy] Missing env file: services/ltx-worker/service.env",
                "[Deploy] Configure connection and secret settings in the dashboard Lambda Config panel.",
            ]
        )
        self.assertEqual(classification.category, "missing_env_file")
        self.assertTrue(classification.safe_to_auto_apply)
        action = resolve_repair_action(classification, retry_number=0, retry_limit=1)
        self.assertEqual(action.id, "use_lambda_config_panel")
        self.assertFalse(action.retry_allowed)

    def test_nebius_ip_missing_is_provider_config_not_model_config(self):
        classification = classify_failure(
            [
                "[Deploy] NEBIUS_IP missing in Nebius provider config",
                "[Deploy] NEBIUS_IP is provider host configuration, not an LTX model setting.",
                "[Deploy] Set it in services/ltx-worker/provider.nebius.env or use the Lambda preset path.",
            ]
        )
        self.assertEqual(classification.category, "provider_host_config_missing")
        self.assertFalse(classification.safe_to_auto_apply)
        action = resolve_repair_action(classification, retry_number=0, retry_limit=1)
        self.assertEqual(action.id, "manual_provider_host_config_missing")
        self.assertFalse(action.retry_allowed)


if __name__ == "__main__":
    unittest.main()
