FROM python:3.11-slim

WORKDIR /app

# Install dependencies required for Prisma engine download and some build tools
RUN apt-get update && apt-get install -y openssl git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate Prisma client
RUN prisma generate

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
