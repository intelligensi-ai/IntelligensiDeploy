FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV COMFYUI_HOME=/opt/ComfyUI
ENV COMFYUI_REF=master

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${COMFYUI_REF}" https://github.com/comfyanonymous/ComfyUI.git "${COMFYUI_HOME}"

WORKDIR ${COMFYUI_HOME}

RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir -r requirements.txt

COPY requirements-extra.txt /tmp/requirements-extra.txt
RUN if [ -s /tmp/requirements-extra.txt ]; then pip3 install --no-cache-dir -r /tmp/requirements-extra.txt; fi

COPY custom_nodes/ /opt/bootstrap/custom_nodes/
COPY workflows/ /opt/bootstrap/workflows/
COPY scripts/ /opt/bootstrap/scripts/
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh /opt/bootstrap/scripts/install_nodes.sh /opt/bootstrap/scripts/download_models.sh

EXPOSE 8188

ENTRYPOINT ["/entrypoint.sh"]

