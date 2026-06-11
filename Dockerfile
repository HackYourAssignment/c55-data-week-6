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

# TODO Task 4: copy requirements.txt (must appear before any COPY src command)

# TODO Task 4: install dependencies with pip

# TODO Task 4: copy the src/ folder
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
# TODO Task 4: set the CMD to run the pipeline (python -m src.pipeline)
CMD ["python", "-m", "src.pipeline"]
