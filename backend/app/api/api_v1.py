from fastapi import APIRouter
from app.api.routes import health, auth, dashboard, tickets, chat, knowledge, classification, agent, notifications, analytics, sla

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(tickets.router)
api_router.include_router(tickets.groups_router)
api_router.include_router(chat.router)
api_router.include_router(knowledge.router)
api_router.include_router(classification.router)
api_router.include_router(agent.router)
api_router.include_router(notifications.router)
api_router.include_router(analytics.router)
api_router.include_router(sla.router)
