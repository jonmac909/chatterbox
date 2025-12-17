FROM runpod/pytorch:2.4.0-py3.11-cuda12.1.1-runtime

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy repo
COPY . .

# Python deps
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Chatterbox in editable mode
RUN pip install -e .

# RunPod serverless entrypoint
CMD ["python", "handler.py"]
