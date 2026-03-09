from fastapi import APIRouter
from app.api.routes import auth, conversations, model_cards, practice, problems, reviews
from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.admin_llm import router as admin_llm_router
from app.api.routes.admin_email import router as admin_email_router
from app.api.routes.password_reset import router as password_reset_router
from app.api.routes.srs import router as srs_router
from app.api.routes.statistics import router as statistics_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.challenges import router as challenges_router
from app.api.routes.resources import router as resources_router
from app.api.routes.notes import router as notes_router
from app.api.cog_test import router as cog_test_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(password_reset_router)
api_router.include_router(problems.router)
api_router.include_router(model_cards.router)
api_router.include_router(conversations.router)
api_router.include_router(practice.router)
api_router.include_router(reviews.router)
api_router.include_router(srs_router)
api_router.include_router(statistics_router)
api_router.include_router(retrieval_router)
api_router.include_router(challenges_router)
api_router.include_router(resources_router)
api_router.include_router(notes_router)

api_router.include_router(admin_users_router)
api_router.include_router(admin_llm_router)
api_router.include_router(admin_email_router)
api_router.include_router(cog_test_router)
