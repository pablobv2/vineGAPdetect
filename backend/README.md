# VineDetect Backend (FastAPI)

Backend API para integrar inferencia YOLO + XAI con el frontend React.

## Requisitos

1. Modelo entrenado disponible en:
   `vineGAPdetect-main/models/trained/best.pt`
2. Dependencias Python:

```bash
pip install -r requirements.txt
```

## Ejecutar

Desde `backend/`:

```bash
uvicorn app.main:app --reload --port 8000
```

## Endpoints

- `GET /api/v1/health`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`
- `GET /api/v1/users` (`admin`)
- `POST /api/v1/users` (`admin`)
- `PATCH /api/v1/users/{user_id}` (`admin`)
- `POST /api/v1/users/{user_id}/reset-password` (`admin`)
- `DELETE /api/v1/users/{user_id}` (`admin`)
- `GET /api/v1/model/info`
- `POST /api/v1/preview` (multipart/form-data)
- `POST /api/v1/jobs/inference` (multipart/form-data)
- `POST /api/v1/jobs/xai` (multipart/form-data)
- `GET /api/v1/jobs/{job_id}`
- `DELETE /api/v1/jobs/{job_id}`

## Variables de entorno (opcionales)

- `FRONTEND_ORIGIN` (default: `http://localhost:5173`)
- `MODEL_RELATIVE_PATH`
- `DEVICE` (`cuda:0`, `cpu`, etc)
- `MAX_UPLOAD_MB`
- `USERS_FILE_RELATIVE_PATH`
- `AUTH_SESSION_TTL_MINUTES`

## Usuarios por defecto

- `admin` / `admin123`
- `operario1` / `operario123`

Los usuarios se guardan en `backend/data/users.json`. Para un TFG esta solución es adecuada como capa de autenticación y autorización de prototipo, sin depender de un servicio externo.
