# 1. Use official Python image
FROM python:3.13-slim

# 2. Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Create and set workdir
WORKDIR /app

# 4. Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy requirements and install
COPY requirements.txt /app/
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# 6. Copy application code
COPY ./dataset.csv /app/
COPY ./main.py /app/

# 7. Expose the Dash port
EXPOSE 80

# 8. Define default command
CMD ["python", "main.py"]