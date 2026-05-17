import json
from pathlib import Path

from app.models.parsed_document import ParsedDocument


def _title(document: ParsedDocument) -> str:
    meta = document.metadata_json or {}
    return meta.get("extracted_title") or meta.get("title") or "Документ"


def document_to_json(document: ParsedDocument) -> str:
    meta = document.metadata_json or {}
    payload = {
        "id": document.id,
        "task_id": document.task_id,
        "source_url": document.source_url,
        "title": _title(document),
        "content_hash": document.content_hash,
        "version": document.version,
        "raw_text": document.raw_text,
        "clean_text": document.clean_text,
        "rewritten_text": document.rewritten_text,
        "metadata_json": meta,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def document_to_markdown(document: ParsedDocument) -> str:
    meta = document.metadata_json or {}
    title = _title(document)
    lines = [
        f"# {title}",
        "",
        f"**Источник:** {document.source_url}",
        f"**Hash:** `{document.content_hash}`",
        f"**Парсер:** {meta.get('parser_name', '—')}",
        "",
        "## Очищенный текст",
        "",
        document.clean_text or "",
        "",
        "## Переписанный текст",
        "",
        document.rewritten_text or "",
        "",
        "## Метаданные",
        "",
        "```json",
        json.dumps(meta, ensure_ascii=False, indent=2),
        "```",
    ]
    return "\n".join(lines)


def write_export_file(document: ParsedDocument, export_type: str, base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    if export_type == "json":
        path = base_dir / f"document_{document.id}.json"
        path.write_text(document_to_json(document), encoding="utf-8")
    else:
        path = base_dir / f"document_{document.id}.md"
        path.write_text(document_to_markdown(document), encoding="utf-8")
    return path
