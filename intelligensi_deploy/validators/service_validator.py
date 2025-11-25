import os
import yaml
from typing import List

REQUIRED_TOP_LEVEL = [
    "Dockerfile",
    "deploy_config.yaml"
]

def validate_service(service_path: str) -> List[str]:
    errors = []

    # 1. Ensure folder exists
    if not os.path.isdir(service_path):
        return [f"Service folder not found: {service_path}"]

    # 2. Top-level required files
    for item in REQUIRED_TOP_LEVEL:
        if not os.path.exists(os.path.join(service_path, item)):
            errors.append(f"Missing required file: {item}")

    # 3. Validate deploy_config.yaml
    config_path = os.path.join(service_path, "deploy_config.yaml")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            if "service_name" not in config:
                errors.append("deploy_config.yaml is missing key: service_name")

            if "docker" not in config:
                errors.append("deploy_config.yaml is missing key: docker")

            if "resources" not in config:
                errors.append("deploy_config.yaml is missing key: resources")

        except Exception as e:
            errors.append(f"deploy_config.yaml parse error: {e}")

    return errors
