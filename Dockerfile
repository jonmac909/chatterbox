FROM runpod/base:0.6.2-cuda12.1.0

WORKDIR /app

# System deps for audio
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir \
    torch \
    torchaudio \
    runpod \
    soundfile \
    numpy

# App code
COPY . .

CMD ["python", "handler.py"]
