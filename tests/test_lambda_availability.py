import unittest
from types import SimpleNamespace
from unittest.mock import patch

import deploy.workflow as workflow
from infra.lambda_api import Instance, LambdaAPIError, LambdaGpuOption, normalize_instance_type_options, rank_gpu_options
from deploy.workflow import _candidate_instance_types


SAMPLE_INSTANCE_TYPES = {
    "data": {
        "gpu_1x_a10": {
            "instance_type": {
                "name": "gpu_1x_a10",
                "description": "1x A10",
                "gpu_description": "A10",
                "price_cents_per_hour": 86,
                "specs": {"vcpus": 30, "memory_gib": 226, "storage_gib": 1300, "gpus": 1},
            },
            "regions_with_capacity_available": [{"name": "us-east-1", "description": "Virginia"}],
        },
        "gpu_1x_a100": {
            "instance_type": {
                "name": "gpu_1x_a100",
                "description": "1x A100",
                "gpu_description": "A100",
                "price_cents_per_hour": 120,
                "specs": {"vcpus": 30, "memory_gib": 200, "storage_gib": 1000, "gpus": 1},
            },
            "regions_with_capacity_available": [{"name": "us-east-1", "description": "Virginia"}],
        },
        "gpu_1x_h100": {
            "instance_type": {
                "name": "gpu_1x_h100",
                "description": "1x H100",
                "gpu_description": "H100",
                "price_cents_per_hour": 300,
                "specs": {"vcpus": 30, "memory_gib": 200, "storage_gib": 1000, "gpus": 1},
            },
            "regions_with_capacity_available": [],
        },
    }
}


class FakePreset:
    name = "image-server-v13"
    instance_type = "gpu_1x_h100"
    region = "us-east-1"


class FakeClient:
    def list_available_gpu_options(self, region):
        return normalize_instance_type_options(SAMPLE_INSTANCE_TYPES, region=region)


class LambdaAvailabilityTests(unittest.TestCase):
    def test_normalizes_instance_type_capacity(self):
        options = normalize_instance_type_options(SAMPLE_INSTANCE_TYPES, region="us-east-1")
        a10 = next(option for option in options if option.instance_type_name == "gpu_1x_a10")
        self.assertTrue(a10.available)
        self.assertEqual(a10.gpu_memory_gb, 24.0)
        self.assertEqual(a10.price_cents_per_hour, 86)

    def test_rank_prefers_available_region_and_cost(self):
        options = normalize_instance_type_options(SAMPLE_INSTANCE_TYPES, region="us-east-1")
        ranked = rank_gpu_options("image-server-v13", options, "us-east-1")
        self.assertEqual(ranked[0].instance_type_name, "gpu_1x_a10")
        self.assertTrue(ranked[0].available)
        self.assertIn("capacity reported", ranked[0].rank_reason)
        self.assertEqual(ranked[-1].instance_type_name, "gpu_1x_h100")
        self.assertFalse(ranked[-1].available)

    def test_rank_marks_below_memory_option_unavailable(self):
        option = LambdaGpuOption(
            instance_type_name="gpu_tiny",
            region_name="us-east-1",
            gpu_description="Tiny GPU",
            gpu_count=1,
            gpu_memory_gb=12.0,
            vcpu_count=8,
            memory_gb=64,
            storage_gb=500,
            price_cents_per_hour=10,
            available=True,
            availability_reason="Capacity currently reported by Lambda.",
            raw={},
        )
        ranked = rank_gpu_options("image-server-v13", [option], "us-east-1")
        self.assertFalse(ranked[0].available)
        self.assertIn("12", ranked[0].rank_reason)

    def test_candidate_instance_types_selected_first_then_ranked_without_duplicates(self):
        candidates = _candidate_instance_types(FakeClient(), FakePreset())
        self.assertEqual(candidates, ["gpu_1x_h100", "gpu_1x_a10", "gpu_1x_a100"])

    def test_deploy_retries_next_ranked_gpu_on_capacity_failure(self):
        attempts = []

        class FallbackClient:
            def __init__(self, *args, **kwargs):
                pass

            def list_available_gpu_options(self, region):
                return normalize_instance_type_options(SAMPLE_INSTANCE_TYPES, region=region)

            def create_instance(self, instance_type, ssh_key_name):
                attempts.append(instance_type)
                if instance_type == "gpu_1x_h100":
                    raise LambdaAPIError("Lambda API error 400: insufficient-capacity")
                return Instance(id="inst-1", ip="203.0.113.10", status="active")

            def wait_for_instance(self, instance_id):
                return Instance(id=instance_id, ip="203.0.113.10", status="active")

        preset = SimpleNamespace(
            name="image-server-v13",
            lambda_api_key="key",
            region="us-east-1",
            instance_type="gpu_1x_h100",
            ssh_key_name="ssh-key",
            ssh_private_key_path="/tmp/key",
            ssh_username="ubuntu",
            env={},
            docker_image="image",
            port=8080,
            health_path="/health",
        )

        with patch.dict("os.environ", {"HF_TOKEN": "token"}), \
            patch.object(workflow, "_get_preset", return_value=preset), \
            patch.object(workflow, "_read_states", return_value={}), \
            patch.object(workflow, "_write_states"), \
            patch.object(workflow, "_bootstrap_remote"), \
            patch.object(workflow, "_append_deploy_log"), \
            patch.object(workflow, "_record_workflow_event"), \
            patch.object(workflow, "_record_runtime_selection"), \
            patch.object(workflow, "_record_repair"), \
            patch.object(workflow, "LambdaClient", FallbackClient):
            state = workflow.deploy_preset("image-server-v13")

        self.assertEqual(attempts, ["gpu_1x_h100", "gpu_1x_a10"])
        self.assertEqual(state.ip, "203.0.113.10")


if __name__ == "__main__":
    unittest.main()
