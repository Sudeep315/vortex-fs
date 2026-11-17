from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/v1/registry", tags=["Feature Registry & Metadata"])


@router.get("")
async def get_full_registry():
    """Returns all registered entities, feature views, and schemas."""
    from vortex.api.app import get_client
    client = get_client()
    return client.registry.to_dict()


@router.get("/entities")
async def list_entities():
    """Lists all registered domain entities."""
    from vortex.api.app import get_client
    client = get_client()
    return [e.model_dump() for e in client.registry.list_entities()]


@router.get("/feature-views")
async def list_feature_views():
    """Lists all registered feature views with their schema, features, and sliding window aggregations."""
    from vortex.api.app import get_client
    client = get_client()
    return [fv.to_dict() for f in [client.registry.list_feature_views()] for fv in f]


@router.get("/feature-views/{name}")
async def get_feature_view_detail(name: str):
    """Retrieve detailed specification and aggregation graph for a specific FeatureView."""
    from vortex.api.app import get_client
    client = get_client()
    fv = client.registry.get_feature_view(name)
    if not fv:
        raise HTTPException(status_code=404, detail=f"FeatureView '{name}' not found")
    return fv.to_dict()
