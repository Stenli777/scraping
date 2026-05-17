from app.rewriters.base import BaseRewriter


class MockRewriter(BaseRewriter):
    """Minimal rewrite stage for end-to-end pipeline testing."""

    provider_name = "mock"

    def rewrite(self, text: str, metadata: dict | None = None) -> str:
        title = (metadata or {}).get("title", "Статья")
        header = f"# {title}\n\n"
        body = text.strip()
        return (
            f"{header}"
            f"> Переписано mock-rewriter (замените на CLIProxyAPI / LM Studio).\n\n"
            f"{body}"
        )
