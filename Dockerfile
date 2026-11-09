FROM python:3.12-slim
RUN pip install --no-cache-dir tzdata
WORKDIR /opt/media-cleanup
COPY cleanup.py docker_bridge.py scheduler.py healthcheck.py ./
ENV TZ=Asia/Shanghai PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-u", "/opt/media-cleanup/scheduler.py"]
