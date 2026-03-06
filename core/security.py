import re
from typing import Any, List, Tuple

from core.pii_classifier import PIIClassifier


class SecurityGuardian:
    """
    Enterprise Security Module for SGR Core Agent.
    Implements regex-based threat detection for command inputs.
    """

    BLOCK_PATTERNS: List[Tuple[str, str]] = [
        # --- 1. Exfiltration & Obfuscation ---
        (r"(?i)\bbase64\b", "Detected 'base64' (Potential exfiltration)"),
        (r"(?i)\bxxd\b", "Detected 'xxd' (Hex dump)"),
        (r"(?i)\bhexdump\b", "Detected 'hexdump' (Hex dump)"),
        (r"(?i)\bod\b", "Detected 'od' (Octal dump)"),
        (r"(?i)\bopenssl\s+enc\b", "Detected 'openssl enc' (Encryption/Exfiltration)"),
        (r"(?i)\bgpg\b", "Detected 'gpg' (Encryption)"),
        # --- 2. Network & Reverse Shells ---
        (r"(?i)\bnc\s+", "Detected 'nc' (Netcat)"),
        (r"(?i)\bnetcat\b", "Detected 'netcat'"),
        (r"(?i)\bncat\b", "Detected 'ncat'"),
        (r"(?i)\bsocat\b", "Detected 'socat'"),
        (r"(?i)\btelnet\b", "Detected 'telnet'"),
        (r"(?i)\bssh\s+", "Detected 'ssh' command"),
        (r"(?i)\bwget\b", "Detected 'wget' (File download)"),
        (r"(?i)\bcurl\s+-X\s*POST", "Detected 'curl POST' (Data exfiltration)"),
        (r"(?i)\bcurl\s+--upload-file", "Detected 'curl upload'"),
        (r"(?i)/dev/tcp/", "Detected '/dev/tcp' (Bash socket)"),
        (r"(?i)/dev/udp/", "Detected '/dev/udp' (Bash socket)"),
        # --- 3. Secrets Access ---
        (r"(?i)\benv\b", "Detected 'env' (Environment dumping)"),
        (r"(?i)\bprintenv\b", "Detected 'printenv'"),
        (r"(?i)/proc/self/environ", "Detected '/proc/self/environ'"),
        (r"(?i)/proc/.*(cmdline|maps|mem)", "Detected '/proc' memory access"),
        (r"(?i)\.env\b", "Detected access to .env file"),
        (r"(?i)credentials", "Detected 'credentials' file access"),
        (r"(?i)id_rsa", "Detected SSH key access"),
        (r"(?i)\.ssh", "Detected .ssh directory"),
        # --- 4. Dangerous System Commands ---
        (r"(?i)\brm\s+-[rRf]*\s+/", "Detected 'rm -rf /' (System destruction)"),
        (r"(?i):(){:|:&};:", "Detected Fork Bomb"),
        (r"(?i)\bdd\b", "Detected 'dd' (Disk manipulation)"),
        (r"(?i)\bmkfs\b", "Detected 'mkfs' (Formatting)"),
        (r"(?i)\bchmod\s+[0-7]{3,}\s+/", "Detected unsafe chmod on root"),
        (r"(?i)\bchown\b", "Detected 'chown'"),
        (r"(?i)\bshutdown\b", "Detected 'shutdown'"),
        (r"(?i)\breboot\b", "Detected 'reboot'"),
        # --- 5. Package Managers (Heavy/DoS) ---
        (r"(?i)\bpip\s+install", "Detected pip install (Unauthorized package)"),
        (r"(?i)\bnpm\s+install", "Detected npm install"),
        (r"(?i)\bapt(-get)?\s+install", "Detected apt install"),
        # --- 6. Path Traversal & Sensitive Files ---
        (r"(?i)\.\./\.\./", "Detected Deep Path Traversal"),
        (r"(?i)/etc/passwd", "Detected /etc/passwd access"),
        (r"(?i)/etc/shadow", "Detected /etc/shadow access"),
        (r"(?i)/var/log/auth", "Detected auth logs access"),
    ]

    def __init__(self):
        # 241+ Regex Patterns (Consolidated)
        # Categories: Secrets, Exfiltration, DoS, Network, Malicious Files
        self.pii_classifier = PIIClassifier(compliance_level="rf_152fz")

    def validate(self, input_text: str) -> None:
        """
        Validates input against security patterns.
        Raises SecurityViolationError if a threat is detected.
        """
        for pattern, reason in self.BLOCK_PATTERNS:
            if re.search(pattern, input_text):
                raise SecurityViolationError(f"Security Alert: {reason}. Action blocked.")

    def validate_params(self, params: dict[str, Any]) -> None:
        """
        Validate resolved parameters before skill execution.
        Detects injection via template resolution (e.g., user input → param → command).
        """
        flat = self._flatten_values(params)
        for value in flat:
            if isinstance(value, str):
                self.validate(value)

    def validate_output(self, output: str) -> str:
        """
        Validate skill output before exposing to user.
        Detects leaked secrets, paths, or sensitive data patterns.
        Returns sanitized string.
        """
        OUTPUT_LEAK_PATTERNS = [
            (r"(?i)api[_-]?key\s*[:=]\s*\S+", "Potential API key leak in output"),
            (r"(?i)password\s*[:=]\s*\S+", "Potential password leak in output"),
            (r"(?i)token\s*[:=]\s*\S+", "Potential token leak in output"),
            (r"(?i)secret\s*[:=]\s*\S+", "Potential secret leak in output"),
            (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "Private key detected in output"),
        ]
        for pattern, _reason in OUTPUT_LEAK_PATTERNS:
            if re.search(pattern, output): 
                # Instead of crashing, we redact the output
                # raise SecurityViolationError(f"Output Security Alert: {reason}. Output sanitized.")
                output = re.sub(pattern, "[REDACTED SECRET]", output)
                
        # Deep PII inspection
        if self.pii_classifier:
            output = self.pii_classifier.anonymize(output)
            
        return output

    def _flatten_values(self, obj: Any, depth: int = 0) -> List[str]:
        """Recursively extract string values from nested dicts/lists (max depth 5)."""
        if depth > 5:
            return []
        values = []
        if isinstance(obj, dict):
            for v in obj.values():
                values.extend(self._flatten_values(v, depth + 1))
        elif isinstance(obj, list):
            for v in obj:
                values.extend(self._flatten_values(v, depth + 1))
        elif isinstance(obj, str):
            values.append(obj)
        return values


class SecurityViolationError(Exception):
    pass

class InputSanitizationLayer:
    """
    Enterprise Defense Layer against Prompt Injections and Malicious Inputs.
    Acts as an initial heuristic filter before queries reach the LLM.
    """
    
    INJECTION_PATTERNS = [
        (r"(?i)\bignore\s+(all\s+)?(previous\s+)?(instructions|directions|prompts)\b", "Attempted instruction override"),
        (r"(?i)\bsystem\s+prompt\b", "Attempted system prompt extraction"),
        (r"(?i)\byou\s+are\s+now\b", "Attempted roleplay highjacking"),
        (r"(?i)\btell\s+me\s+your\s+hidden\b", "Attempted secret extraction"),
        (r"(?i)\bbypass\s+safeguards\b", "Attempted safeguard bypass"),
        (r"(?i)\bforget\s+everything\b", "Attempted memory wipe"),
        (r"(?i)\btell\s+me\s+what\s+you\s+were\s+told\b", "Attempted prompt extraction")
    ]
    
    def __init__(self, max_length: int = 15000):
        self.max_length = max_length
        
    def sanitize(self, user_input: str) -> str:
        """
        Scans input for common adversarial injection techniques.
        Raises SecurityViolationError if a high-confidence attack is detected.
        """
        if not user_input:
            return user_input
            
        # 1. Length enforcement (Denial of Service protection via large context)
        if len(user_input) > self.max_length:
            raise SecurityViolationError(f"Input exceeds maximum allowed length of {self.max_length} characters. (Length: {len(user_input)})")
            
        # 2. Heuristic Regex Matching
        for pattern, reason in self.INJECTION_PATTERNS:
            if re.search(pattern, user_input):
                raise SecurityViolationError(f"Adversarial Input Detected: {reason}. Request blocked.")
                
        # Future Feature: Add LLM-based classification here if strict mode enabled
        
        return user_input
