"""FastAPI server for Flux-1 Schnell image generation."""

from __future__ import annotations

import base64
import io
from typing import Optional

import torch
from diffusers import DiffusionPipeline
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Flux Schnell Image Server")


class GenerateRequest(BaseModel):
    prompt: str
    width: Optional[int] = 1024
    height: Optional[int] = 1024


pipe = DiffusionPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell",
    torch_dtype=torch.float16,
).to("cuda")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/generate")
def generate(req: GenerateRequest) -> dict:
    try:
        image = pipe(req.prompt, width=req.width, height=req.height).images[0]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return {"image_base64": encoded}
