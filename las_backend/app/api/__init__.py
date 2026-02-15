from fastapi import APIRouter
from app.api.routes import auth, problems, model_cards, conversations, practice

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(problems.router)
api_router.include_router(model_cards.router)
api_router.include_router(conversations.router)
api_router.include_router(practice.router)
api_router.include_router(practice.router_reviews)
