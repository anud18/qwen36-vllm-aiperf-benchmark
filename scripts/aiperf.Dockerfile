FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip setuptools wheel cython numpy
RUN pip install --no-cache-dir aiperf
ENTRYPOINT ["aiperf"]
