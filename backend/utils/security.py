import re
from typing import Tuple


def detect_prompt_injection(text: str) -> Tuple[bool, str]:
    """
    Detect potential prompt injection attempts in user input.
    
    Returns:
        (is_bad: bool, reason: str)
    """
    if not text or not isinstance(text, str):
        return False, ""
    
    text_lower = text.lower()
    
    # Common prompt injection patterns
    injection_patterns = [
        # Direct instruction patterns
        r"ignore (all )?previous (instructions|prompts|rules)",
        r"disregard (all )?previous (instructions|prompts|rules)",
        r"forget (all )?previous (instructions|prompts|rules)",
        r"ignore (all )?(the )?above",
        r"disregard (all )?(the )?above",
        
        # Role manipulation
        r"you are now",
        r"act as (a |an )?",
        r"pretend (you are|to be)",
        r"simulate (a |an )?",
        r"roleplay as",
        
        # System prompt extraction
        r"what (are|were) your (initial )?instructions",
        r"show me your (system )?prompt",
        r"reveal your (system )?prompt",
        r"print your (system )?prompt",
        r"what (are|is) your (system )?prompt",
        
        # Output manipulation
        r"output (only|just)",
        r"respond (only|just) with",
        r"say (only|just)",
        r"print (only|just)",
        r"return (only|just)",
        
        # Jailbreak attempts
        r"dan mode",
        r"developer mode",
        r"jailbreak",
        r"evil mode",
        
        # Instruction injection
        r"new instructions?:",
        r"system:",
        r"assistant:",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
    ]
    
    # Check for patterns
    for pattern in injection_patterns:
        if re.search(pattern, text_lower):
            return True, f"Detected potential prompt injection pattern: '{pattern}'"
    
    # Check for excessive instructions (likely not code)
    instruction_keywords = [
        "ignore", "disregard", "forget", "pretend", "act as",
        "you are", "your role", "new instructions", "system prompt"
    ]
    
    keyword_count = sum(1 for kw in instruction_keywords if kw in text_lower)
    if keyword_count >= 3:
        return True, "Input contains multiple instruction-like phrases suggesting prompt injection"
    
    # Check for suspicious special tokens
    special_tokens = ["<|endoftext|>", "[INST]", "[/INST]", "<|system|>", "<|user|>", "<|assistant|>"]
    for token in special_tokens:
        if token in text:
            return True, f"Input contains special model token: {token}"
    
    return False, ""