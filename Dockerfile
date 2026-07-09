# Use the official Python image
FROM python:3.13-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Show Python output immediately
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker cache optimization)
COPY requirements.txt .

# Install Python packages
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the entire project
COPY . .


RUN chmod +x entrypoint.sh

# Expose Daphne's port
EXPOSE 8000