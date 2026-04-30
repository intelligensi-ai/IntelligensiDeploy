FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install \
    diffusers==0.33.1 \
    transformers==4.49.0 \
    accelerate==1.1.1 \
    hf_transfer \
    safetensors \
    imageio \
    imageio-ffmpeg \
    sentencepiece \
    protobuf

COPY . .

CMD ["python", "worker.py"]
