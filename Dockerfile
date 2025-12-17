FROM runpod/pytorch:2.4.0-py3.11-cuda12.1.0-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --upgrade pip \
    && pip install -e . \
    && pip install soundfile runpod

CMD ["python", "handler.py"]
