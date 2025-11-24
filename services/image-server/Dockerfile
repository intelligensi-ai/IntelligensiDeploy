FROM nvidia/cuda:12.8.0-base-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3 python3-pip git libgl1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt .
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["bash", "./start.sh"]
