FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .
RUN pip install --no-cache-dir -e .

# Ensure output directory exists
RUN mkdir -p outputs

CMD ["python", "run_pipeline.py", "--mode", "full"]
