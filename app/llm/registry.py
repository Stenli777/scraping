"""Registry facade — re-exports routing for centralized access."""

from app.llm.models import ModelRoute
from app.llm.routing import list_aliases, resolve_route


def resolve_model_route(model_alias: str) -> ModelRoute:
    return resolve_route(model_alias)


__all__ = ["resolve_model_route", "list_aliases", "ModelRoute"]
