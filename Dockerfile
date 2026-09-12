FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p keys logs/snapshots

ENV CONTROLLER_ID=ctrl_01
ENV PYTHONUNBUFFERED=1

# Dashboard port. Controller OpenFlow and gossip ports are declared
# per-service in docker-compose.yml via network_mode: host.
EXPOSE 5000

CMD ["python3", "dashboard/app.py"]
