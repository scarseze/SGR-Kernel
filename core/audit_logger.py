import os
import asyncio
import hmac
import hashlib
import json
import datetime
import logging
from typing import Any, Dict

logger = logging.getLogger("audit_logger")

class ComplianceAuditLogger:
    def __init__(self, log_dir: str = None):
        self.log_dir = log_dir or os.getenv("LOG_DIR", "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "audit_152fz.log")
        
        # Secret key for HMAC signature
        self.secret_key = os.environ.get("AUDIT_SECRET_KEY", "dev_secret_key_change_in_prod")
        if self.secret_key == "dev_secret_key_change_in_prod":
            logger.warning("Using default AUDIT_SECRET_KEY. This is unsafe for production.")

    def _generate_hmac(self, data: str) -> str:
        h = hmac.new(self.secret_key.encode('utf-8'), data.encode('utf-8'), hashlib.sha256)
        return h.hexdigest()

    def log_event(self, event_type: str, session_id: str, details: Dict[str, Any]):
        timestamp = datetime.datetime.now(datetime.UTC).isoformat()
        
        payload = {
            "timestamp": timestamp,
            "event_type": event_type,
            "session_id": session_id,
            "details": details
        }
        
        payload_str = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        signature = self._generate_hmac(payload_str)
        
        log_entry = {
            "payload": payload,
            "signature": signature
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {str(e)}")

    async def log_event_async(self, event_type: str, session_id: str, details: Dict[str, Any]):
        """Non-blocking version of log_event running in a separate thread."""
        await asyncio.to_thread(self.log_event, event_type, session_id, details)

    def verify_logs(self) -> bool:
        """
        Verify the integrity of all records in the audit log.
        Returns True if all records are valid, raises ValueError otherwise.
        """
        if not os.path.exists(self.log_file):
            return True # Nothing to verify
            
        with open(self.log_file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    payload_str = json.dumps(entry["payload"], ensure_ascii=False, sort_keys=True)
                    expected_signature = self._generate_hmac(payload_str)
                    
                    if not hmac.compare_digest(entry["signature"], expected_signature):
                        raise ValueError(f"Audit log integrity check failed at line {i+1}")
                except json.JSONDecodeError:
                    raise ValueError(f"Corrupted JSON in audit log at line {i+1}")
                    
        return True
