# Aegis inside the cluster: the same loop as on the laptop, plus the dashboard and /metrics on 8080.
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aegis ./aegis
COPY config.yaml .

ENV PYTHONUNBUFFERED=1
USER 65534
EXPOSE 8080
CMD ["python", "-m", "aegis.actuator"]
