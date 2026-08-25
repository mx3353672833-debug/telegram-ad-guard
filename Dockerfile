FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .

# Refresh Debian packages on build so the runtime image picks up current
# security fixes from the base distribution instead of shipping stale layers.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && python -m pip install --upgrade setuptools \
    && python -m pip install -r requirements.txt \
    && python - <<'PY'
import importlib.util
import subprocess
import sys

if importlib.util.find_spec("wheel") is not None:
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "wheel"])
PY

COPY . .

CMD ["python", "bot.py"]
