from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import threading
import time
import uuid


MODEL_ID = os.getenv("LTX_MODEL_ID", "Lightricks/LTX-2.3")
MODEL_VARIANT = os.getenv("LTX_MODEL_VARIANT", "ltx-2.3-22b-distilled")
ENGINE = os.getenv("LTX_ENGINE", "ltx-2.3")
BACKEND = os.getenv("LTX_BACKEND", "ltx2")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/outputs"))
MAX_WIDTH = int(os.getenv("MAX_WIDTH", "3840"))
MAX_HEIGHT = int(os.getenv("MAX_HEIGHT", "2160"))
MAX_FRAMES = int(os.getenv("MAX_FRAMES", "100000"))
MAX_INFERENCE_STEPS = int(os.getenv("MAX_INFERENCE_STEPS", "12"))

jobs = {}
jobs_lock = threading.Lock()


def json_response(handler, status_code, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def get_int(data, key, default, minimum=None, maximum=None):
    value = int(data.get(key, default))
    if minimum is not None and value < minimum:
        raise ValueError(f"{key} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{key} must be at most {maximum}")
    return value


def update_job(job_id, **updates):
    with jobs_lock:
        jobs[job_id].update(updates)


def run_generation(job_id, request):
    started = time.time()
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        update_job(job_id, status="blocked_runtime_integration", started_at=started)
        raise RuntimeError(
            "LTX 2.3 worker scaffold is running, but generation is not wired yet. "
            "Use the official LTX-2 pipeline integration before enabling production renders."
        )
    except Exception as exc:
        update_job(
            job_id,
            status="error",
            error=str(exc),
            seconds=round(time.time() - started, 2),
        )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/jobs/"):
            job_id = path.removeprefix("/jobs/").strip("/")
            with jobs_lock:
                job = jobs.get(job_id)
            json_response(self, 200, job) if job else json_response(self, 404, {"error": "job_not_found"})
            return

        if path != "/health":
            json_response(self, 404, {"error": "not_found"})
            return

        json_response(
            self,
            200,
            {
                "status": "ready",
                "engine": ENGINE,
                "backend": BACKEND,
                "model_id": MODEL_ID,
                "model_variant": MODEL_VARIANT,
                "generation_ready": False,
                "reason": "LTX 2.3 service scaffold is ready; official pipeline integration is pending.",
            },
        )

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}
            prompt = data.get("prompt", "").strip()
            if not prompt:
                json_response(self, 400, {"error": "prompt is required"})
                return

            width = get_int(data, "width", int(os.getenv("WIDTH", "832")), 32, MAX_WIDTH)
            height = get_int(data, "height", int(os.getenv("HEIGHT", "480")), 32, MAX_HEIGHT)
            num_frames = get_int(data, "num_frames", int(os.getenv("NUM_FRAMES", "97")), 9, MAX_FRAMES)
            steps = get_int(data, "num_inference_steps", int(os.getenv("NUM_INFERENCE_STEPS", "8")), 1, MAX_INFERENCE_STEPS)
            if width % 32 != 0 or height % 32 != 0:
                raise ValueError("width and height must be divisible by 32")
            if (num_frames - 1) % 8 != 0:
                raise ValueError("LTX 2.3 frame count must satisfy (num_frames - 1) % 8 == 0")

            job_id = str(uuid.uuid4())
            job = {
                "id": job_id,
                "status": "queued",
                "engine": ENGINE,
                "backend": BACKEND,
                "model_id": MODEL_ID,
                "model_variant": MODEL_VARIANT,
                "settings": {
                    "width": width,
                    "height": height,
                    "num_frames": num_frames,
                    "num_inference_steps": steps,
                    "seed": data.get("seed"),
                },
            }
            with jobs_lock:
                jobs[job_id] = job
            threading.Thread(target=run_generation, args=(job_id, job), daemon=True).start()
            json_response(self, 202, job)
        except Exception as exc:
            json_response(self, 500, {"status": "error", "error": str(exc)})


server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
print("LTX 2.3 worker scaffold running on port 8000...", flush=True)
server.serve_forever()
