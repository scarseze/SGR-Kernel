import re
import structlog
from typing import List, Dict, Any

logger = structlog.get_logger(__name__)

class PIIClassifier:
    """
    Mock integration of a True ML-based Named Entity Recognition (NER) pipeline (like Microsoft Presidio).
    In a real implementation, this would call a local ML model (e.g. RuBERT) or an external API
    to token classification. For this mock, it simulates the ML interface but falls back to 
    advanced heuristics under the hood.
    """
    def __init__(self, compliance_level: str = "rf_152fz"):
        self.compliance_level = compliance_level
        self.confidence_threshold = 0.85
        logger.info("pii_classifier_initialized", backend="mock_ml_ner", compliance_level=self.compliance_level)

    def _analyze_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Simulates the output of an ML NER model.
        Returns a list of identified entities with start/end indices, entity type, and confidence score.
        """
        findings = []
        
        # Simulated ML predictions (using regex internally to mock the NER locations)
        # PHONE pattern tightened: require at least 10 digit characters to avoid matching short numeric IDs
        patterns = {
            "EMAIL": (r'[\w.-]+@[\w.-]+\.\w+', 0.99),
            "API_KEY": (r'sk-[a-zA-Z0-9]{20,}', 0.98),
            "PHONE": (r'\+?\d[\d\s\-\(\)]{9,}\d', 0.90)
        }
        
        if self.compliance_level == "rf_152fz":
            patterns.update({
                "PASSPORT_RF": (r'\b\d{4}\s?\d{6}\b', 0.95),
                "INN": (r'\b\d{12}\b', 0.92),
                "SNILS": (r'\b\d{3}-\d{3}-\d{3}\s?\d{2}\b', 0.94),
                "CARD_RF": (r'\b\d{4}[ \-]?\d{4}[ \-]?\d{4}[ \-]?\d{4}\b', 0.88),
                "PHONE_RU": (r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', 0.96)
            })
            
        elif self.compliance_level in ["gdpr", "hipaa"]:
            patterns.update({
                "CREDIT_CARD": (r'\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b', 0.88),
                "IP_ADDRESS": (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 0.90)
            })
            if self.compliance_level == "hipaa":
                patterns.update({
                    "MEDICAL_DATE": (r'\b\d{2}[-/]\d{2}[-/]\d{4}\b', 0.86),
                    "MEDICAL_ID": (r'\b(?:SSN|Patient ID|MRN)[:\s-]*\d+\b', 0.95)
                })

        for entity_type, (pattern, confidence) in patterns.items():
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                if confidence >= self.confidence_threshold:
                    findings.append({
                        "entity_type": entity_type,
                        "start": match.start(),
                        "end": match.end(),
                        "score": confidence,
                        "value": match.group(0)
                    })
        
        # Deduplicate overlapping matches: keep only the highest-confidence match per span
        findings = self._deduplicate_overlaps(findings)
                    
        # Sort findings by start index in reverse to avoid offset shifting when replacing
        findings.sort(key=lambda x: x["start"], reverse=True)
        return findings

    @staticmethod
    def _deduplicate_overlaps(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        When two findings overlap (e.g., PHONE_RU and PHONE match the same substring),
        keep only the one with the higher confidence score. This prevents garbled double-replacements.
        """
        if not findings:
            return findings
            
        # Sort by start index, then by confidence descending
        findings.sort(key=lambda x: (x["start"], -x["score"]))
        
        deduplicated = [findings[0]]
        for current in findings[1:]:
            previous = deduplicated[-1]
            # Check if current overlaps with the last kept finding
            if current["start"] < previous["end"]:
                # Overlap detected: keep the one with higher confidence
                if current["score"] > previous["score"]:
                    deduplicated[-1] = current
                # else: keep previous (already in the list)
            else:
                deduplicated.append(current)
                
        return deduplicated

    def anonymize(self, text: str) -> str:
        """
        Redacts text based on the ML classification results.
        """
        if not text:
            return text
            
        findings = self._analyze_text(text)
        if not findings:
            return text
            
        anonymized_text = text
        for finding in findings:
            start = finding["start"]
            end = finding["end"]
            entity_type = finding["entity_type"]
            replacement = f"[REDACTED_{entity_type}]"
            
            # Replace the substring
            anonymized_text = anonymized_text[:start] + replacement + anonymized_text[end:]
            
        return anonymized_text
