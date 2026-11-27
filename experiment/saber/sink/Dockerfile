FROM python:3.14-slim-trixie

COPY server.py /server.py
USER 65532:65532
EXPOSE 80
HEALTHCHECK --interval=1s --timeout=2s --retries=5 \
    CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1', 80), 1).close()"]
ENTRYPOINT ["python", "-u", "/server.py"]
