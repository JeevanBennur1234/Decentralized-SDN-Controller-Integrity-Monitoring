FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p keys logs/snapshots

ENV CONTROLLER_ID=ctrl_01
ENV PYTHONUNBUFFERED=1

EXPOSE 5000 6633 9101

CMD ["python3", "dashboard/app.py"]
