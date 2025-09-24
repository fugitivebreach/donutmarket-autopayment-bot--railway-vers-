# Use Node.js 18 base image
FROM node:18-bullseye-slim

# Install Python 3.9 and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package.json and package-lock.json early
COPY package*.json ./

# Configure npm registry
RUN npm config set registry https://registry.npmjs.org/

# Install packages
RUN npm install --no-optional --production --timeout=60000

# Update packages
RUN npm update --no-optional --production --timeout=60000

# Copy requirements.txt and install Python dependencies
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 3000

# Start the application
CMD ["python", "start.py"]
