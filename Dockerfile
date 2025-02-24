# Use the official lightweight Python image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install required packages
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose port 8080
EXPOSE 8080

# Run the application using Gunicorn with settings from Procfile
CMD gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
