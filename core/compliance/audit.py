import datetime
import json
from pathlib import Path


class AuditLogger:
    """
    Generates an irrefutable JSON audit trail of all compliance checks
    performed for each session. Each audit report can be presented to
    regulatory auditors (Roskomnadzor, GDPR DPA, etc.).
    """

    def __init__(self, output_dir: str = "logs/compliance"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(self, session_id: str, audit_log: list, status: str) -> str:
        report = {
            "session_id": session_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "overall_status": status,
            "checks": audit_log,
        }
        filename = self.output_dir / f"compliance_{session_id}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return str(filename)
