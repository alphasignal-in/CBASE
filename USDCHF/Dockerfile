# -------------------------
# Stage 1: compile python -> pyc
# -------------------------
FROM python:3.9-slim AS builder

WORKDIR /build

COPY . .

# compile all .py files to .pyc (-b keeps compiled next to source)
RUN python -m compileall -b -q .

# collect compiled files and scripts
RUN mkdir -p /compiled && \
    find . -name "*.pyc" -exec cp {} /compiled/ \; || true && \
    cp start.sh autoupdate.sh /compiled/ 2>/dev/null || true

# -------------------------
# Stage 2: runtime
# -------------------------
FROM python:3.9-slim

WORKDIR /USDCHF

COPY requirements.txt /USDCHF/requirements.txt

# install only what we need for runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl jq gcc gfortran libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r /USDCHF/requirements.txt

# copy compiled code + scripts only
COPY --from=builder /compiled /USDCHF

RUN chmod +x /USDCHF/start.sh /USDCHF/autoupdate.sh || true

ENV PYTHONUNBUFFERED=1

CMD ["sh", "/USDCHF/start.sh"]