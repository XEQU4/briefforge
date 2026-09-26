from fastapi import APIRouter

from app.api.routes import auth, organizations, proposals, tasks, teams


product_router = APIRouter()
for route_module in (auth, organizations, tasks, proposals, teams):
    product_router.include_router(route_module.router)

v1_router = APIRouter(prefix="/api/v1")
# Keep the static proposal history path ahead of the dynamic
# PATCH /proposals/{proposal_id} route included below.
v1_router.include_router(proposals.versioned_list_router)
v1_router.include_router(product_router)
for route_module in (tasks, teams):
    v1_router.include_router(route_module.versioned_list_router)

api_router = APIRouter()
api_router.include_router(product_router)
for route_module in (tasks, proposals, teams):
    api_router.include_router(route_module.legacy_list_router)
api_router.include_router(v1_router)
