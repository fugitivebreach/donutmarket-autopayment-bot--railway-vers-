# Use Python 3.11 with Node.js
FROM python:3.11-slim

# Install Node.js 18
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files
COPY requirements.txt package.json package-lock.json ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies
RUN npm install

# Copy application code
COPY . .

# Expose port for Railway
EXPOSE 3000

# Start the application
CMD ["python", "start.py"]
