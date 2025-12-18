FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install the chatterbox package
RUN pip install --no-cache-dir -e .

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Run the handler
CMD ["python", "-u", "handler.py"]
