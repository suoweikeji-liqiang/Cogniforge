from fastapi import APIRouter
from app.api.routes import auth, problems, model_cards, conversations, practice
from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.admin_llm import router as admin_llm_router
from app.api.routes.admin_email import router as admin_email_router
from app.api.routes.password_reset import router as password_reset_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(password_reset_router)
api_router.include_router(problems.router)
api_router.include_router(model_cards.router)
api_router.include_router(conversations.router)
api_router.include_router(practice.router)
api_router.include_router(practice.router_reviews)

api_router.include_router(admin_users_router)
api_router.include_router(admin_llm_router)
api_router.include_router(admin_email_router)
