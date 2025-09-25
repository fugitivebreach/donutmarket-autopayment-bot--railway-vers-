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

# Install Node.js packages individually to avoid hanging
RUN npm config set registry https://registry.npmjs.org/
RUN npm install dotenv@16.3.1 --no-optional --production
RUN npm install mysql2@3.6.5 --no-optional --production --timeout=60000
RUN npm install express@4.18.2 --no-optional --production --timeout=60000
RUN npm install axios@1.6.0 --no-optional --production --timeout=60000
RUN npm uninstall mineflayer@4.33.0 --no-optional --production --timeout=60000
RUN npm install mineflayer@4.33.0 --no-optional --production --timeout=60000
RUN npm install minecraft-protocol@1.62.0 --no-optional --production --timeout=60000
RUN npm uninstall prismarine-auth@2.7.0 --no-optional --production --timeout=60000
RUN npm install prismarine-auth@2.7.0 --no-optional --production --timeout=60000
RUN npm uninstall @xboxreplay/xboxlive-auth@5.1.0 --no-optional --production --timeout=60000
RUN npm install @xboxreplay/xboxlive-auth@5.1.0 --no-optional --production --timeout=60000

# Copy requirements.txt and install Python dependencies
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Expose port
EXPOSE 3000

# Start the application
CMD ["python", "start.py"]
