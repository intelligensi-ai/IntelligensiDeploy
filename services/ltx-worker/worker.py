from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import gc
import json
import os
import threading
import time
import traceback
import uuid

import torch
from diffusers import LTXPipeline
from diffusers.utils import export_to_video


MODEL_ID = os.getenv("LTX_MODEL_ID", "Lightricks/LTX-Video")
ENGINE = os.getenv("LTX_ENGINE", "ltx-video")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/outputs"))
DEFAULT_NEGATIVE_PROMPT = os.getenv(
    "NEGATIVE_PROMPT",
    "worst quality, inconsistent motion, blurry, jittery, distorted",
)
LOW_VRAM = os.getenv("LOW_VRAM", "1").lower() not in ("0", "false", "no")
MAX_WIDTH = int(os.getenv("MAX_WIDTH", "256"))
MAX_HEIGHT = int(os.getenv("MAX_HEIGHT", "256"))
MAX_FRAMES = int(os.getenv("MAX_FRAMES", "17"))
MAX_INFERENCE_STEPS = int(os.getenv("MAX_INFERENCE_STEPS", "4"))

pipe = None
pipe_lock = threading.Lock()
generation_lock = threading.Lock()
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


def get_float(data, key, default, minimum=None, maximum=None):
    value = float(data.get(key, default))
    if minimum is not None and value < minimum:
        raise ValueError(f"{key} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{key} must be at most {maximum}")
    return value


def select_dtype():
    dtype = os.getenv("LTX_DTYPE", "auto").lower()
    if dtype == "float32":
        return torch.float32
    if dtype == "float16":
        return torch.float16
    if dtype == "bfloat16":
        return torch.bfloat16
    if torch.cuda.is_available():
        return torch.float16
    return torch.float32


def load_ltx():
    global pipe

    with pipe_lock:
        if pipe is not None:
            return pipe

        dtype = select_dtype()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading {MODEL_ID} on {device} with {dtype}...", flush=True)

        loaded_pipe = LTXPipeline.from_pretrained(MODEL_ID, torch_dtype=dtype)

        if device == "cuda" and LOW_VRAM:
            loaded_pipe.enable_model_cpu_offload()
        else:
            loaded_pipe.to(device)

        if hasattr(loaded_pipe.vae, "enable_tiling"):
            loaded_pipe.vae.enable_tiling()
        if hasattr(loaded_pipe, "enable_attention_slicing"):
            loaded_pipe.enable_attention_slicing()

        pipe = loaded_pipe
        print("LTX model loaded.", flush=True)
        return pipe


def update_job(job_id, **updates):
    with jobs_lock:
        jobs[job_id].update(updates)


def run_generation(job_id, request):
    try:
        with generation_lock:
            update_job(job_id, status="loading_model")
            pipeline = load_ltx()
            generator = None
            seed = request["seed"]
            if seed is not None:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                generator = torch.Generator(device=device).manual_seed(int(seed))

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            started = time.time()
            update_job(job_id, status="generating", started_at=started)
            print(f"Generating video for prompt: {request['prompt']}", flush=True)

            result = pipeline(
                prompt=request["prompt"],
                negative_prompt=request["negative_prompt"],
                width=request["width"],
                height=request["height"],
                num_frames=request["num_frames"],
                num_inference_steps=request["steps"],
                guidance_scale=request["guidance_scale"],
                decode_timestep=0.05,
                decode_noise_scale=0.025,
                generator=generator,
            )

            filename = f"{job_id}.mp4"
            output_path = OUTPUT_DIR / filename
            export_to_video(result.frames[0], str(output_path), fps=request["fps"])

            update_job(
                job_id,
                status="completed",
                output=str(output_path),
                seconds=round(time.time() - started, 2),
            )
            del result
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    except Exception as exc:
        traceback.print_exc()
        update_job(job_id, status="error", error=str(exc))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/jobs/"):
            job_id = path.removeprefix("/jobs/").strip("/")
            with jobs_lock:
                job = jobs.get(job_id)
            if job is None:
                json_response(self, 404, {"error": "job_not_found"})
            else:
                json_response(self, 200, job)
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
                "model_id": MODEL_ID,
                "model_loaded": pipe is not None,
                "cuda_available": torch.cuda.is_available(),
                "low_vram": LOW_VRAM,
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

            negative_prompt = data.get("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
            width = get_int(data, "width", int(os.getenv("WIDTH", "256")), 32, MAX_WIDTH)
            height = get_int(data, "height", int(os.getenv("HEIGHT", "256")), 32, MAX_HEIGHT)
            num_frames = get_int(data, "num_frames", int(os.getenv("NUM_FRAMES", "17")), 1, MAX_FRAMES)
            steps = get_int(data, "num_inference_steps", int(os.getenv("NUM_INFERENCE_STEPS", "4")), 1, MAX_INFERENCE_STEPS)
            guidance_scale = get_float(data, "guidance_scale", float(os.getenv("GUIDANCE_SCALE", "3.0")), 0.0, 20.0)
            fps = get_int(data, "fps", int(os.getenv("FPS", "24")), 1, 60)
            seed = data.get("seed")

            if width % 32 != 0 or height % 32 != 0:
                raise ValueError("width and height must be divisible by 32")

            job_id = str(uuid.uuid4())
            request = {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "num_frames": num_frames,
                "steps": steps,
                "guidance_scale": guidance_scale,
                "fps": fps,
                "seed": seed,
            }
            job = {
                "id": job_id,
                "status": "queued",
                "engine": ENGINE,
                "model_id": MODEL_ID,
                "settings": {
                    "width": width,
                    "height": height,
                    "num_frames": num_frames,
                    "num_inference_steps": steps,
                    "guidance_scale": guidance_scale,
                    "fps": fps,
                    "seed": seed,
                },
            }
            with jobs_lock:
                jobs[job_id] = job

            worker = threading.Thread(target=run_generation, args=(job_id, request), daemon=True)
            worker.start()

            json_response(self, 202, job)
        except Exception as exc:
            traceback.print_exc()
            json_response(self, 500, {"status": "error", "error": str(exc)})


server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
print("LTX worker running on port 8000...", flush=True)
server.serve_forever()
