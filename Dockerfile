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

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install Node.js dependencies
COPY package.json ./
RUN npm install

# Copy application code
COPY . .

# Expose port for Railway
EXPOSE 3000

# Start the application
CMD ["python", "start.py"]
