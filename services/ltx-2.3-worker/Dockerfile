FROM pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
ENV HF_HUB_ENABLE_HF_TRANSFER=1
ENV LTX_ENGINE=ltx-2.3
ENV LTX_BACKEND=ltx2
ENV LTX_MODEL_ID=Lightricks/LTX-2.3

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl ffmpeg git tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install hf_transfer huggingface_hub imageio imageio-ffmpeg

# The official LTX-2 codebase is the intended runtime path for LTX 2.3.
# Generation wiring remains intentionally explicit in worker.py until the
# exact ltx-pipelines invocation is locked and smoke-tested on a Lambda GPU.
ARG LTX2_REPO=https://github.com/Lightricks/LTX-2.git
ARG LTX2_REF=main
RUN git clone --depth 1 --branch "$LTX2_REF" "$LTX2_REPO" /opt/LTX-2 || \
    git clone --depth 1 "$LTX2_REPO" /opt/LTX-2

COPY . .

CMD ["python", "worker.py"]
