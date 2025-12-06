"""Minimal Lambda Labs API client for provisioning GPU instances."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, Optional
from urllib import error, request

API_BASE = "https://cloud.lambdalabs.com/api/v1"
DEFAULT_USER_AGENT = "IntelligensiDeploy/1.0 (+https://intelligensi.ai)"
DEFAULT_REGION = "us-east-1"


class LambdaAPIError(RuntimeError):
    """Raised when the Lambda Labs API returns an error."""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


@dataclass
class Instance:
    id: str
    ip: Optional[str]
    status: str


class LambdaClient:
    """Tiny wrapper around the Lambda Labs HTTP API."""

    def __init__(self, api_key: str, region: str = DEFAULT_REGION, user_agent: str = DEFAULT_USER_AGENT):
        self.api_key = api_key
        self.region = region or DEFAULT_REGION
        self.user_agent = user_agent

    def _request(self, method: str, path: str, payload: Optional[Dict] = None) -> Dict:
        # Normalise path
        if not path.startswith("/"):
            path = "/" + path
        url = f"{API_BASE}{path}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }

        data = json.dumps(payload).encode() if payload else None
        req = request.Request(url, data=data, headers=headers, method=method)

        try:
            with request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())

        except error.HTTPError as exc:
            body = exc.read().decode(errors="ignore")
            raise LambdaAPIError(f"Lambda API error {exc.code}: {body}", status=exc.code)

        except error.URLError as exc:
            raise LambdaAPIError(f"Unable to reach Lambda API: {exc}")

    def create_instance(
        self,
        instance_type: str,
        ssh_key_name: str,
        instance_name: Optional[str] = None,
    ) -> Instance:

        # Payload shape that returned instance_ids from /instance-operations/launch
        payload = {
            "region_name": self.region,
            "instance_type_name": instance_type,
            "quantity": 1,
            "ssh_key_names": [ssh_key_name],
        }

        if instance_name:
            payload["name"] = instance_name

        data = self._request("POST", "/instance-operations/launch", payload)

        instance_ids = data.get("data", {}).get("instance_ids", [])
        if not instance_ids:
            raise LambdaAPIError("Lambda API did not return instance_ids")

        instance_id = instance_ids[0]

        # Now wait for instance details (get IP)
        return self.wait_for_instance(instance_id)


    def _wait_for_operation(self, operation_id: str, timeout: int = 600) -> Instance:
        start = time.time()
        while True:
            data = self._request("GET", f"/instance-operations/{operation_id}")
            resources = data.get("data", {}).get("resources", {})
            instances = resources.get("instances", [])

            if instances:
                inst = instances[0]
                return Instance(
                    id=inst["id"],
                    ip=inst.get("ip"),
                    status=inst.get("status", "unknown"),
                )

            if time.time() - start > timeout:
                raise LambdaAPIError(f"Timed out waiting for operation {operation_id}")

            time.sleep(5)

    def get_instance(self, instance_id: str) -> Instance:
        data = self._request("GET", f"/instances/{instance_id}")
        inst = data.get("data", {})
        return Instance(
            id=inst.get("id", instance_id),
            ip=inst.get("ip"),
            status=inst.get("status", "unknown"),
        )

    def delete_instance(self, instance_id: str) -> None:
        self._request("DELETE", f"/instances/{instance_id}")

    def wait_for_instance(self, instance_id: str, timeout: int = 900) -> Instance:
        start = time.time()
        last_status = "pending"

        while True:
            instance = self.get_instance(instance_id)
            last_status = instance.status

            if instance.ip:
                return instance

            if time.time() - start > timeout:
                raise LambdaAPIError(
                    f"Timed out waiting for instance {instance_id} (last status: {last_status})"
                )

            time.sleep(10)


__all__ = ["LambdaClient", "Instance", "LambdaAPIError"]
