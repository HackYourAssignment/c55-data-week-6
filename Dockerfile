# Task 4: containerise the pipeline so Azure Container Apps Jobs can run it.
#
# Requirements (mirror Week 5):
# 1. Base image: python:3.11-slim.
# 2. Copy requirements.txt BEFORE copying src/ so the install layer stays cached.
# 3. Install dependencies from requirements.txt.
# 4. Copy src/ into the image.
# 5. Default command runs the pipeline module.

FROM python:3.11-slim

WORKDIR /app

# 1. Copy requirements first
COPY requirements.txt .

# 2. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy source code
COPY src/ src/

# 4. Set environment for python path
ENV PYTHONPATH=/app

# 5. Run pipeline
CMD ["python", "src/pipeline.py"]