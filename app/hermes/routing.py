"""Hermes agent aliases — separate from Scrap LLM aliases."""

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class HermesAgentRoute:
    alias: str
    description: str
    orchestrate_agent: str
    cliproxy_model_alias: str | None = None


HERMES_AGENT_ROUTES: dict[str, HermesAgentRoute] = {
    "hermes-cheap": HermesAgentRoute(
        alias="hermes-cheap",
        description="Fast/cheap Hermes reasoning",
        orchestrate_agent="cheap",
        cliproxy_model_alias="local/classifier-fast",
    ),
    "hermes-smart": HermesAgentRoute(
        alias="hermes-smart",
        description="Balanced Hermes reasoning (default)",
        orchestrate_agent="smart",
        cliproxy_model_alias="local/rewrite-main",
    ),
    "hermes-code": HermesAgentRoute(
        alias="hermes-code",
        description="Code-oriented Hermes agent",
        orchestrate_agent="code",
        cliproxy_model_alias="local/rewrite-main",
    ),
    "hermes-long": HermesAgentRoute(
        alias="hermes-long",
        description="Long-context Hermes agent",
        orchestrate_agent="long",
        cliproxy_model_alias="local/rewrite-main",
    ),
    "hermes-long-smart": HermesAgentRoute(
        alias="hermes-long-smart",
        description="Long-context smart Hermes agent",
        orchestrate_agent="long-smart",
        cliproxy_model_alias="local/rewrite-main",
    ),
}


def list_hermes_aliases() -> list[dict[str, str]]:
    return [
        {"alias": r.alias, "description": r.description}
        for r in HERMES_AGENT_ROUTES.values()
    ]


def resolve_hermes_agent(agent: str | None) -> HermesAgentRoute:
    settings = get_settings()
    key = (agent or settings.hermes_default_agent or "hermes-smart").strip()
    route = HERMES_AGENT_ROUTES.get(key)
    if not route:
        raise ValueError(f"Unknown Hermes agent alias: {key}")
    return route
