# Use official lightweight Python image
FROM python:3.11-slim

# Install required tools
RUN apt-get update && apt-get install -y \
    gosu \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Copy entrypoint script and make executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port (optional)
EXPOSE 5454

# Entrypoint to handle permissions and drop privileges
ENTRYPOINT ["/entrypoint.sh"]

# Default command to run the app
CMD ["python", "app.py"]
