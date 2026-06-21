# 1. Use an official, lightweight Python base image
FROM python:3.9-slim

# 2. Set the working directory in the container
WORKDIR /app

# 3. Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the UI source files and only the aggregated Parquet datasets
COPY ui/ ./ui/
COPY data/*.parquet ./data/

# 6. Expose Port 8080 (Cloud Run's default port)
EXPOSE 8080

# 7. Start Streamlit bound to port 8080 and address 0.0.0.0
CMD ["streamlit", "run", "ui/04_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
