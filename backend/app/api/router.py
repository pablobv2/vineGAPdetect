from fastapi import APIRouter

from app.api.routes import auth, exports, health, history, jobs, model, preview, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(model.router, prefix="/model", tags=["model"])
api_router.include_router(preview.router, prefix="/preview", tags=["preview"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(exports.router, prefix="/export", tags=["export"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
