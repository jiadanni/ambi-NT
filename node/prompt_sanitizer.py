"""
Prompt sanitization and security validation module

Protects against:
- Prompt injection attacks
- Jailbreak attempts
- Excessively long or complex prompts
- Malicious system instructions
- Resource exhaustion attempts
"""

import re
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)


class PromptSanitizer:
    """Validates and sanitizes prompts before sending to LLM."""
    
    # Patterns that indicate potential prompt injection
    INJECTION_PATTERNS = [
        # System instruction overrides
        r"(?i)(ignore|disregard|forget).{0,20}(previous|all|above|prior).{0,20}(instructions|prompts|rules)",
        r"(?i)you.{0,10}are.{0,10}now.{0,10}(a|an)\s+",
        r"(?i)new.{0,10}(instructions|role|system.{0,10}message)",
        r"(?i)system\s*:\s*",
        r"(?i)override.{0,10}(instructions|rules|settings)",
        
        # Jailbreak attempts
        r"(?i)(dan|developer.{0,10}mode|god.{0,10}mode|do.{0,10}anything.{0,10}now)",
        r"(?i)ignore.{0,10}(all\s+)?safety",
        r"(?i)disable.{0,10}(safety|content.{0,10}policy|restrictions)",
        r"(?i)bypass.{0,10}(filter|safety|moderation)",
        
        # Prompt extraction attempts
        r"(?i)(show|reveal|display|print).{0,20}(your|the).{0,20}(prompt|instructions|system.{0,10}message)",
        r"(?i)what.{0,10}(are|is).{0,10}your.{0,10}(original|initial|system).{0,10}(prompt|instructions)",
        
        # Multi-turn manipulation
        r"(?i)in.{0,10}the.{0,10}next.{0,10}(message|response|turn)",
        r"(?i)from.{0,10}now.{0,10}on",
        
        # Code execution attempts
        r"```[\s\S]*?(exec|eval|import\s+os|subprocess|__import__)[\s\S]*?```",
        r"(?i)(execute|run).{0,10}(code|command|script)",
    ]
    
    # Suspicious patterns that warrant logging but may not block
    SUSPICIOUS_PATTERNS = [
        r"(?i)(hack|exploit|vulnerability|inject)",
        r"(?i)unlimited\s+(tokens|compute|resources)",
        r"(?i)ignore\s+(limits|restrictions|rules)",
    ]
    
    def __init__(
        self,
        max_length: int = 10000,
        max_lines: int = 500,
        max_repeated_chars: int = 100,
        enable_injection_detection: bool = True
    ):
        """
        Initialize the prompt sanitizer.
        
        Args:
            max_length: Maximum prompt length in characters
            max_lines: Maximum number of lines
            max_repeated_chars: Maximum consecutive repeated characters
            enable_injection_detection: Whether to check for injection patterns
        """
        self.max_length = max_length
        self.max_lines = max_lines
        self.max_repeated_chars = max_repeated_chars
        self.enable_injection_detection = enable_injection_detection
        
        # Compile patterns for efficiency
        self.injection_regexes = [re.compile(p) for p in self.INJECTION_PATTERNS]
        self.suspicious_regexes = [re.compile(p) for p in self.SUSPICIOUS_PATTERNS]
    
    def validate_prompt(self, prompt: str) -> Tuple[bool, Optional[str], List[str]]:
        """
        Validate a prompt for security issues.
        
        Args:
            prompt: The plaintext prompt to validate
        
        Returns:
            Tuple of (is_valid, error_message, warnings)
        """
        warnings = []
        
        # Check 1: Length validation
        if len(prompt) > self.max_length:
            return False, f"Prompt exceeds maximum length ({self.max_length} chars)", warnings
        
        if len(prompt.strip()) == 0:
            return False, "Prompt is empty", warnings
        
        # Check 2: Line count validation
        lines = prompt.split('\n')
        if len(lines) > self.max_lines:
            return False, f"Prompt exceeds maximum line count ({self.max_lines} lines)", warnings
        
        # Check 3: Repeated character detection (potential DoS)
        if self._has_excessive_repetition(prompt):
            return False, f"Prompt contains excessive character repetition (>{self.max_repeated_chars} chars)", warnings
        
        # Check 4: Control character detection
        if self._has_dangerous_control_chars(prompt):
            return False, "Prompt contains potentially dangerous control characters", warnings
        
        # Check 5: Injection pattern detection
        if self.enable_injection_detection:
            injection_found, injection_type = self._detect_injection(prompt)
            if injection_found:
                logger.warning(f"Potential prompt injection detected: {injection_type}")
                return False, f"Prompt contains potentially malicious content: {injection_type}", warnings
        
        # Check 6: Suspicious patterns (warnings only)
        suspicious_matches = self._detect_suspicious_patterns(prompt)
        if suspicious_matches:
            for match in suspicious_matches:
                warning = f"Suspicious pattern detected: {match}"
                warnings.append(warning)
                logger.info(warning)
        
        # Check 7: Excessive complexity (deeply nested structures)
        if self._is_excessively_complex(prompt):
            warnings.append("Prompt has high structural complexity")
        
        return True, None, warnings
    
    def _has_excessive_repetition(self, text: str) -> bool:
        """Detect excessive character repetition (e.g., 'aaaaaaa....')."""
        max_consecutive = 0
        current_char = None
        current_count = 0
        
        for char in text:
            if char == current_char:
                current_count += 1
                max_consecutive = max(max_consecutive, current_count)
            else:
                current_char = char
                current_count = 1
        
        return max_consecutive > self.max_repeated_chars
    
    def _has_dangerous_control_chars(self, text: str) -> bool:
        """Check for potentially dangerous control characters."""
        # Allow common whitespace: space, tab, newline, carriage return
        allowed_control = {'\t', '\n', '\r', ' '}
        
        for char in text:
            # Check if it's a control character and not in allowed list
            if ord(char) < 32 and char not in allowed_control:
                logger.warning(f"Dangerous control character found: {repr(char)}")
                return True
        
        return False
    
    def _detect_injection(self, text: str) -> Tuple[bool, Optional[str]]:
        """Detect potential prompt injection patterns."""
        for pattern in self.injection_regexes:
            match = pattern.search(text)
            if match:
                # Return the matched pattern (truncated for logging)
                matched_text = match.group(0)[:50]
                return True, f"Pattern matched: {matched_text}"
        
        return False, None
    
    def _detect_suspicious_patterns(self, text: str) -> List[str]:
        """Detect suspicious patterns that warrant logging."""
        matches = []
        for pattern in self.suspicious_regexes:
            match = pattern.search(text)
            if match:
                matches.append(match.group(0)[:30])
        
        return matches
    
    def _is_excessively_complex(self, text: str) -> bool:
        """Detect excessively complex prompts that might cause issues."""
        # Count nesting level of brackets/braces
        max_nesting = 0
        current_nesting = 0
        
        for char in text:
            if char in '({[<':
                current_nesting += 1
                max_nesting = max(max_nesting, current_nesting)
            elif char in ')}]>':
                current_nesting = max(0, current_nesting - 1)
        
        # Warn if nesting exceeds 10 levels
        return max_nesting > 10
    
    def estimate_token_count(self, text: str) -> int:
        """
        Rough estimate of token count (for resource planning).
        
        Uses a simple heuristic: ~4 characters per token on average.
        This is conservative for English text.
        """
        return len(text) // 4 + len(text.split())
    
    def estimate_compute_cost(self, text: str) -> str:
        """
        Estimate computational cost category.
        
        Returns: 'low', 'medium', 'high', or 'extreme'
        """
        token_estimate = self.estimate_token_count(text)
        
        if token_estimate < 100:
            return 'low'
        elif token_estimate < 500:
            return 'medium'
        elif token_estimate < 2000:
            return 'high'
        else:
            return 'extreme'
