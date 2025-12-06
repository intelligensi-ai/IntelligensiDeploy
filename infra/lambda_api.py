"""Minimal Lambda Labs API client for provisioning GPU instances."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, Optional
from urllib import error, request

API_BASE = "https://cloud.lambdalabs.com/api/v1"
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

    def __init__(self, api_key: str, region: str = DEFAULT_REGION):
        self.api_key = api_key
        self.region = region or DEFAULT_REGION

    def _request(self, method: str, path: str, payload: Optional[Dict] = None) -> Dict:
        url = f"{API_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode() if payload else None
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except error.HTTPError as exc:  # type: ignore[attr-defined]
            body = exc.read().decode(errors="ignore")
            raise LambdaAPIError(f"Lambda API error {exc.code}: {body}", status=exc.code)
        except error.URLError as exc:  # type: ignore[attr-defined]
            raise LambdaAPIError(f"Unable to reach Lambda API: {exc}")

    def create_instance(
        self,
        instance_type: str,
        ssh_key_name: str,
        name: str = "image-server",
    ) -> Instance:
        payload = {
            "region_name": self.region,
            "instance_type_name": instance_type,
            "quantity": 1,
            "name": name,
            "ssh_key_names": [ssh_key_name],
        }
        data = self._request("POST", "/instances", payload)
        instances = data.get("data", {}).get("instances") or []
        if not instances:
            raise LambdaAPIError("Lambda API did not return an instance identifier")
        inst = instances[0]
        return Instance(id=inst["id"], ip=inst.get("ip"), status=inst.get("status", "unknown"))

    def get_instance(self, instance_id: str) -> Instance:
        data = self._request("GET", f"/instances/{instance_id}")
        inst = data.get("data", {})
        return Instance(id=inst.get("id", instance_id), ip=inst.get("ip"), status=inst.get("status", "unknown"))

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
                raise LambdaAPIError(f"Timed out waiting for instance {instance_id} (last status: {last_status})")
            time.sleep(10)


__all__ = ["LambdaClient", "Instance", "LambdaAPIError"]
