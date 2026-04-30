"""Minimal Lambda Labs API client for provisioning GPU instances."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
from urllib import error, request

API_BASE = "https://cloud.lambdalabs.com/api/v1"
DEFAULT_USER_AGENT = "IntelligensiDeploy/1.0 (+https://intelligensi.ai)"
DEFAULT_REGION = "us-east-1"
WORKLOAD_GPU_REQUIREMENTS_GB = {
    "image-server": 24.0,
    "image-server-v13": 24.0,
    "flux": 24.0,
    "flux_image_server": 24.0,
    "ltx-worker": 24.0,
    "ltx-worker-lambda": 24.0,
    "ltx-worker-nebius-dev": 24.0,
    "comfyui": 48.0,
    "comfyui-nebius-dev": 48.0,
    "comfyui-nebius-prod": 48.0,
}
KNOWN_GOOD_GPU_FAMILIES = ("a10", "l40s", "a100", "h100")


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


@dataclass
class LambdaRegion:
    name: str
    description: str = ""


@dataclass
class LambdaGpuOption:
    instance_type_name: str
    region_name: str
    gpu_description: str
    gpu_count: int
    gpu_memory_gb: Optional[float]
    vcpu_count: Optional[int]
    memory_gb: Optional[float]
    storage_gb: Optional[float]
    price_cents_per_hour: Optional[int]
    available: bool
    availability_reason: str
    raw: Dict[str, Any]
    rank_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LambdaClient:
    """Tiny wrapper around the Lambda Labs HTTP API."""

    def __init__(
        self,
        api_key: str,
        region: str = DEFAULT_REGION,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.region = region or DEFAULT_REGION
        self.user_agent = user_agent
        self.timeout = timeout

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
            with request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())

        except error.HTTPError as exc:
            body = exc.read().decode(errors="ignore")
            raise LambdaAPIError(f"Lambda API error {exc.code}: {body}", status=exc.code)

        except error.URLError as exc:
            raise LambdaAPIError(f"Unable to reach Lambda API: {exc}")

    def list_instance_types(self) -> Dict[str, Any]:
        return self._request("GET", "/instance-types")

    def list_regions(self) -> Dict[str, Any]:
        try:
            return self._request("GET", "/regions")
        except LambdaAPIError as exc:
            if exc.status == 404:
                data = self.list_instance_types()
                regions: Dict[str, Dict[str, str]] = {}
                for option in normalize_instance_type_options(data):
                    if option.region_name:
                        regions[option.region_name] = {
                            "name": option.region_name,
                            "description": "",
                        }
                return {"data": sorted(regions.values(), key=lambda item: item["name"])}
            raise

    def list_available_gpu_options(
        self,
        region: Optional[str] = None,
        min_gpu_memory_gb: Optional[float] = None,
    ) -> List[LambdaGpuOption]:
        data = self.list_instance_types()
        return normalize_instance_type_options(data, region=region, min_gpu_memory_gb=min_gpu_memory_gb)

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
        self._request("POST", "/instance-operations/terminate", {"instance_ids": [instance_id]})

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


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().lower().replace("gib", "").replace("gb", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _integer(value: Any) -> Optional[int]:
    number = _number(value)
    return int(number) if number is not None else None


def _extract_gpu_memory_gb(instance_type: Dict[str, Any]) -> Optional[float]:
    specs = instance_type.get("specs", {})
    for key in ("gpu_memory_gib", "gpu_memory_gb", "memory_per_gpu_gib", "memory_per_gpu_gb"):
        value = _number(specs.get(key) or instance_type.get(key))
        if value is not None:
            return value

    text = " ".join(
        str(value)
        for value in (
            instance_type.get("name"),
            instance_type.get("description"),
            instance_type.get("gpu_description"),
        )
        if value
    ).lower()
    known_memory = {
        "h100": 80,
        "a100": 40,
        "a10": 24,
        "l40s": 48,
        "rtx 6000": 48,
        "a6000": 48,
    }
    for needle, memory_gb in known_memory.items():
        if needle in text:
            return float(memory_gb)
    return None


def normalize_instance_type_options(
    response: Dict[str, Any],
    region: Optional[str] = None,
    min_gpu_memory_gb: Optional[float] = None,
) -> List[LambdaGpuOption]:
    data = response.get("data", response)
    if not isinstance(data, dict):
        return []

    options: List[LambdaGpuOption] = []
    region_filter = region.strip() if isinstance(region, str) and region.strip() else None
    for fallback_name, item in data.items():
        if not isinstance(item, dict):
            continue
        instance_type = item.get("instance_type", item)
        if not isinstance(instance_type, dict):
            continue

        instance_type_name = str(instance_type.get("name") or fallback_name)
        raw_regions = item.get("regions_with_capacity_available") or []
        if isinstance(raw_regions, dict):
            raw_regions = list(raw_regions.values())

        regions: List[LambdaRegion] = []
        for raw_region in raw_regions:
            if isinstance(raw_region, str):
                regions.append(LambdaRegion(name=raw_region))
            elif isinstance(raw_region, dict) and raw_region.get("name"):
                regions.append(
                    LambdaRegion(
                        name=str(raw_region.get("name")),
                        description=str(raw_region.get("description") or ""),
                    )
                )

        if region_filter:
            target_regions = [item for item in regions if item.name == region_filter]
            if not target_regions:
                target_regions = [LambdaRegion(name=region_filter)]
        else:
            target_regions = regions or [LambdaRegion(name="")]

        specs = instance_type.get("specs", {})
        gpu_memory_gb = _extract_gpu_memory_gb(instance_type)
        price = _integer(instance_type.get("price_cents_per_hour"))
        vcpus = _integer(specs.get("vcpus") or specs.get("vcpu_count"))
        memory = _number(specs.get("memory_gib") or specs.get("memory_gb"))
        storage = _number(specs.get("storage_gib") or specs.get("storage_gb"))
        gpu_count = _integer(specs.get("gpus") or specs.get("gpu_count")) or 0
        gpu_description = str(instance_type.get("gpu_description") or instance_type.get("description") or "")

        for target_region in target_regions:
            has_capacity = any(available_region.name == target_region.name for available_region in regions)
            enough_memory = min_gpu_memory_gb is None or gpu_memory_gb is None or gpu_memory_gb >= min_gpu_memory_gb
            available = has_capacity and enough_memory
            if not has_capacity:
                availability_reason = "No current capacity reported for this region."
            elif not enough_memory:
                availability_reason = f"Below requested {min_gpu_memory_gb:g} GB GPU memory."
            else:
                availability_reason = "Capacity currently reported by Lambda."

            options.append(
                LambdaGpuOption(
                    instance_type_name=instance_type_name,
                    region_name=target_region.name,
                    gpu_description=gpu_description,
                    gpu_count=gpu_count,
                    gpu_memory_gb=gpu_memory_gb,
                    vcpu_count=vcpus,
                    memory_gb=memory,
                    storage_gb=storage,
                    price_cents_per_hour=price,
                    available=available,
                    availability_reason=availability_reason,
                    raw=item,
                )
            )

    return sorted(
        options,
        key=lambda option: (
            not option.available,
            option.price_cents_per_hour if option.price_cents_per_hour is not None else 10**9,
            -(option.gpu_memory_gb or 0),
            option.instance_type_name,
        ),
    )


def minimum_gpu_memory_for_workload(workload: str) -> Optional[float]:
    normalized = (workload or "").strip().lower()
    if normalized in WORKLOAD_GPU_REQUIREMENTS_GB:
        return WORKLOAD_GPU_REQUIREMENTS_GB[normalized]
    if "comfy" in normalized:
        return 48.0
    if "ltx" in normalized or "video" in normalized or "flux" in normalized or "image" in normalized:
        return 24.0
    return None


def _known_family_rank(option: LambdaGpuOption) -> int:
    haystack = f"{option.instance_type_name} {option.gpu_description}".lower()
    for index, family in enumerate(KNOWN_GOOD_GPU_FAMILIES):
        if family in haystack:
            return index
    return len(KNOWN_GOOD_GPU_FAMILIES)


def rank_gpu_options(
    workload: str,
    options: List[LambdaGpuOption | Dict[str, Any]],
    region: Optional[str],
    cost_ceiling: Optional[int] = None,
) -> List[LambdaGpuOption]:
    minimum_memory = minimum_gpu_memory_for_workload(workload)
    preferred_region = (region or "").strip()
    normalized_options = [
        option if isinstance(option, LambdaGpuOption) else LambdaGpuOption(**{**option, "raw": option.get("raw", {})})
        for option in options
    ]
    ranked: List[LambdaGpuOption] = []

    for option in normalized_options:
        reasons: List[str] = []
        has_region = not preferred_region or option.region_name == preferred_region
        has_memory = minimum_memory is None or option.gpu_memory_gb is None or option.gpu_memory_gb >= minimum_memory
        within_cost = cost_ceiling is None or option.price_cents_per_hour is None or option.price_cents_per_hour <= cost_ceiling

        if option.available:
            reasons.append("capacity reported")
        else:
            reasons.append("no capacity reported")
        if has_region and preferred_region:
            reasons.append(f"matches {preferred_region}")
        elif preferred_region:
            reasons.append(f"outside {preferred_region}")
        if minimum_memory is not None:
            reasons.append(
                f"{option.gpu_memory_gb:g} GB GPU memory"
                if option.gpu_memory_gb is not None
                else f"GPU memory unknown; requires {minimum_memory:g} GB"
            )
        if option.price_cents_per_hour is not None:
            reasons.append(f"${option.price_cents_per_hour / 100:.2f}/hr")
        if not within_cost:
            reasons.append("above cost ceiling")

        ranked.append(
            LambdaGpuOption(
                **{
                    **option.to_dict(),
                    "available": option.available and has_region and has_memory and within_cost,
                    "rank_reason": "; ".join(reasons),
                }
            )
        )

    return sorted(
        ranked,
        key=lambda option: (
            not option.available,
            option.region_name != preferred_region if preferred_region else False,
            option.price_cents_per_hour if option.price_cents_per_hour is not None else 10**9,
            _known_family_rank(option),
            -(option.gpu_memory_gb or 0),
            option.instance_type_name,
        ),
    )


__all__ = [
    "LambdaClient",
    "Instance",
    "LambdaRegion",
    "LambdaGpuOption",
    "LambdaAPIError",
    "minimum_gpu_memory_for_workload",
    "normalize_instance_type_options",
    "rank_gpu_options",
]
