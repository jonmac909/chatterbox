FROM runpod/pytorch:2.4.0-py3.11-cuda12.1.0-runtime

WORKDIR /app

ENV PYTHONPATH=/app/src

RUN apt-get update && apt-get install -y ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "handler.py"]
