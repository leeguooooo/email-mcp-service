FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Create accounts.json placeholder if it doesn't exist
RUN touch accounts.json && echo "[]" > accounts.json

# Create a non-root user
RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src:/app

# The command will be provided by smithery.yaml
CMD ["python", "smithery_wrapper.py"]