# vineGAPdetect

Sistema para la detección automática de marras en viñedos a partir de ortomosaicos georreferenciados. El proyecto combina un pipeline experimental de visión por computador con una aplicación web para inferencia, visualización, explicabilidad y exportación de resultados.

## Objetivo

El repositorio recoge: construcción de datasets YOLO-OBB, entrenamiento y evaluación de modelos, servicio backend de inferencia y frontend de inspección geoespacial.

## Estructura

```text
vinegapdetect/
|-- backend/              API FastAPI, persistencia, inferencia, XAI y exportaciones
|-- frontend/             Aplicación React + TypeScript + OpenLayers
|-- ml/                   Pipeline experimental de dataset, entrenamiento y evaluación
|-- docs/                 Documentación técnica de arquitectura y reproducibilidad
|-- docker-compose.yml    Despliegue local completo
`-- README.md
```

## Componentes principales

- `ml/`: scripts reproducibles para generar datasets YOLO-OBB, entrenar modelos Ultralytics, comparar configuraciones, evaluar en test y generar mapas CAM.
- `backend/`: API REST para autenticación, previsualización, inferencia por slicing, trabajos asíncronos, historial, XAI y exportación GeoPackage.
- `frontend/`: interfaz web para carga de ortomosaicos, visualización de detecciones, ajuste de umbral, XAI, historial y exportación de informes.

## Requisitos

- Python 3.10 o superior.
- Node.js 20 o superior.
- Docker y Docker Compose para despliegue integrado.
- Modelo entrenado en `ml/models/trained/best.pt` para ejecutar inferencia.
- Datos geoespaciales privados fuera de Git, ubicados localmente en `ml/data/raw/` cuando se ejecute el pipeline experimental.

## Ejecución local

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

La aplicación queda disponible en `http://localhost:5173` y consume la API en `http://localhost:8000/api/v1`.

### Docker Compose

```bash
docker compose up --build
```

El despliegue sirve el frontend en `http://localhost` y levanta el backend como servicio interno.

## Modelo y datos

El repositorio no versiona datos crudos, bases de datos locales, resultados de entrenamiento ni pesos de modelos. Para ejecutar la aplicación de inferencia se debe colocar el checkpoint final en:

```text
ml/models/trained/best.pt
```

Las carpetas `ml/data/`, `ml/results/`, `ml/models/pretrained/` y `ml/models/trained/` incluyen `.gitkeep` para conservar la estructura sin incluir artefactos pesados o privados.

## Usuarios iniciales

En el primer arranque, si no existe base de datos local, el backend crea usuarios de demostración:

```text
admin / admin123
operario1 / operario123
```
