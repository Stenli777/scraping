"""Placeholder preview — no GPU / no external image API."""

import hashlib
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.media.base import BaseMediaProvider
from app.media.schemas import MediaGenerateResult

PLACEHOLDER_WIDTH = 1200
PLACEHOLDER_HEIGHT = 630


class PlaceholderMediaProvider(BaseMediaProvider):
    name = "placeholder"

    def _storage_dir(self) -> Path:
        settings = get_settings()
        now = datetime.now(timezone.utc)
        base = settings.media_storage_root
        return base / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"

    def generate_preview(
        self,
        *,
        prompt: str,
        alt_text: str,
        caption: str,
        document_id: int,
        negative_prompt: str | None = None,
    ) -> MediaGenerateResult:
        dest_dir = self._storage_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"doc{document_id}-preview-{uuid4().hex[:12]}.svg"
        path = dest_dir / filename

        title = (alt_text or "Preview").replace("&", "&amp;").replace("<", "&lt;")
        sub = textwrap.shorten(prompt or caption or "Scrap placeholder", width=80)
        sub = sub.replace("&", "&amp;").replace("<", "&lt;")
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PLACEHOLDER_WIDTH}" height="{PLACEHOLDER_HEIGHT}" '
            f'viewBox="0 0 {PLACEHOLDER_WIDTH} {PLACEHOLDER_HEIGHT}">\n'
            '  <rect width="100%" height="100%" fill="#1a1a2e"/>\n'
            f'  <rect x="40" y="40" width="{PLACEHOLDER_WIDTH - 80}" height="{PLACEHOLDER_HEIGHT - 80}" '
            'rx="12" fill="#16213e" stroke="#0f3460" stroke-width="2"/>\n'
            f'  <text x="80" y="140" fill="#e94560" font-family="system-ui,sans-serif" '
            f'font-size="36" font-weight="700">{title}</text>\n'
            f'  <text x="80" y="220" fill="#a8b2d1" font-family="system-ui,sans-serif" font-size="22">'
            f'Document #{document_id} · placeholder</text>\n'
            f'  <text x="80" y="280" fill="#8892b0" font-family="system-ui,sans-serif" font-size="18">{sub}</text>\n'
            '</svg>'
        )
        data = svg.encode("utf-8")
        path.write_bytes(data)
        checksum = hashlib.sha256(data).hexdigest()
        settings = get_settings()
        rel = path.relative_to(settings.media_storage_root)
        return MediaGenerateResult(
            success=True,
            storage_path=str(rel).replace("\\", "/"),
            mime_type="image/svg+xml",
            width=PLACEHOLDER_WIDTH,
            height=PLACEHOLDER_HEIGHT,
            checksum=checksum,
            metadata={"provider": self.name, "negative_prompt": negative_prompt},
        )
