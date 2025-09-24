# Use official Node.js image with Python
FROM node:18-slim

# Install Python 3.11
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-pip \
    python3.11-venv \
    && ln -s /usr/bin/python3.11 /usr/bin/python \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Node.js dependencies first (faster)
COPY package.json ./
RUN npm install --production --no-optional

# Copy and install Python dependencies
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for Railway
EXPOSE 3000

# Start the application
CMD ["python", "start.py"]
