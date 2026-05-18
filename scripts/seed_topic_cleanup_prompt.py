"""Seed topic_cleanup_v1 prompt template in DB."""
from app.db.session import SessionLocal
from app.services.prompt_service import PROMPT_KEYS

def main() -> None:
    if "topic_cleanup_v1" not in PROMPT_KEYS:
        print("topic_cleanup_v1 not in PROMPT_KEYS")
        return
    print("topic_cleanup_v1 available via code_fallback; DB seed optional")

if __name__ == "__main__":
    main()
