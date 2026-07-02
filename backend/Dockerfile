FROM python:3.11-slim

WORKDIR /app

# libgl1 + libglib2.0-0: requeridos por opencv-python
# libgomp1: OpenMP para numpy / torch
# curl: usado por el healthcheck de docker-compose
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# PyTorch + torchvision CPU (deben instalarse juntos desde el ?ndice CPU
# para garantizar compatibilidad de versiones; si se instalan por separado,
# ultralytics descarga torchvision desde PyPI con ruedas CUDA incompatibles).
RUN pip install --no-cache-dir torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu

# Resto de dependencias (torch/torchvision ya satisfechos, se excluyen).
COPY backend/requirements.txt /tmp/requirements.txt
RUN grep -vE "^(torch|torchvision)" /tmp/requirements.txt \
    | pip install --no-cache-dir -r /dev/stdin

# C?digo fuente
COPY backend/ ./backend/
COPY ml/scripts/ ./ml/scripts/

# Estos directorios se rellenan en tiempo de ejecuci?n mediante vol?menes.
RUN mkdir -p ml/models/trained backend/data

EXPOSE 8000

# Igual que en desarrollo local: ejecutar desde backend/ con "app.main:app".
# config.py usa parents[3] desde backend/app/core/config.py -> /app (repo root),
# as? que las rutas de modelo y datos siguen resolviendo correctamente.
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

