# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory to /app
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Cloud Run listens on port 8080 by default
ENV PORT 8080

# Use gunicorn to serve the Flask app.
# Assumes your Flask app instance is defined as "app" in main.py.
CMD exec gunicorn --bind :$PORT --workers 5 main:app
