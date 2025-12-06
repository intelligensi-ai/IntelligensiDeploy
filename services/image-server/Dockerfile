FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime

RUN apt-get update && apt-get install -y git python3-pip && rm -rf /var/lib/apt/lists/*

RUN pip install fastapi uvicorn[standard] accelerate torchvision \
    transformers diffusers safetensors xformers

WORKDIR /app
COPY server.py /app/server.py

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
