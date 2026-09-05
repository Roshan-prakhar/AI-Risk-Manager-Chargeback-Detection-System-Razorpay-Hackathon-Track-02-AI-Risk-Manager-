FROM python:3.11-slim

WORKDIR /app

# Copy everything
COPY . .

# Install serving deps only
RUN pip install --no-cache-dir -r fraudguard_api/requirements.txt

# Expose port
EXPOSE 8000

# Start the unified API
CMD ["uvicorn", "fraudguard_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
