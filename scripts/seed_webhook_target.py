import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.session import SessionLocal
from app.models.project import Project
from app.models.publish_target import PublishTarget

db = SessionLocal()
project = db.query(Project).filter_by(slug="crmflow24").first()
if project:
    existing = (
        db.query(PublishTarget)
        .filter_by(project_id=project.id, name="crmflow24-webhook-test")
        .first()
    )
    if not existing:
        t = PublishTarget(
            project_id=project.id,
            name="crmflow24-webhook-test",
            target_type="webhook",
            endpoint_url="http://127.0.0.1:19999/publish",
            auth_type="none",
            enabled=True,
            dry_run=False,
            default_status="draft",
            payload_format="article_v1",
        )
        db.add(t)
        db.commit()
        print("created", t.id)
    else:
        print("exists", existing.id)
db.close()
