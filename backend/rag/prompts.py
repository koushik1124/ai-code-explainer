EXPLAIN_PROMPT = """You are an expert software engineer and code reviewer.

Analyze the following {language} code and provide a detailed explanation.

CONTEXT FROM KNOWLEDGE BASE:
{context}

CODE TO ANALYZE:
```{language}
{code}
```

CRITICAL INSTRUCTIONS:
1. Return ONLY a valid JSON object
2. No markdown code blocks (no ```json or ```)
3. No additional text before or after the JSON
4. Follow the EXACT structure below

REQUIRED JSON STRUCTURE:
{{
  "overview": "A 2-3 sentence summary of what this code does",
  "step_by_step": [
    "First, the code does X...",
    "Then it performs Y...",
    "Finally, it returns Z..."
  ],
  "potential_bugs": [
    "Bug: Description of the issue and why it could cause problems",
    "Bug: Another potential issue to watch out for"
  ],
  "improvements": [
    "Use more descriptive variable names like 'userCount' instead of 'n'",
    "Add error handling for edge case when input is null",
    "Consider extracting this logic into a separate function for reusability"
  ],
  "complexity": {{
    "time": "O(n) - Linear time because it iterates through the array once",
    "space": "O(1) - Constant space as no additional data structures are used",
    "overall": "This code is efficient for small to medium datasets"
  }},
  "citations": [
    {{"source": "documentation.md", "snippet": "Relevant excerpt from context"}},
    {{"source": "best_practices.txt", "snippet": "Another relevant excerpt"}}
  ]
}}

REMEMBER: Output ONLY the JSON object. Start with {{ and end with }}. No other text.
"""

TEST_PROMPT = """You are a senior QA engineer specializing in test automation.

Generate comprehensive unit tests for the following {language} code.

CODE TO TEST:
```{language}
{code}
```

CRITICAL INSTRUCTIONS:
1. Return ONLY a valid JSON object
2. No markdown code blocks (no ```json or ```)
3. No additional text before or after the JSON
4. Follow the EXACT structure below

REQUIRED JSON STRUCTURE:
{{
  "test_file_name": "test_example.py",
  "test_code": "import unittest\\n\\nclass TestExample(unittest.TestCase):\\n    def test_something(self):\\n        self.assertEqual(1, 1)",
  "test_cases_covered": [
    "Tests normal input with valid data",
    "Tests edge case with empty input",
    "Tests error handling for invalid input",
    "Tests boundary conditions"
  ],
  "how_to_run": "Run with: python -m unittest test_example.py"
}}

IMPORTANT NOTES:
- Use \\n for newlines in the test_code string
- Escape quotes properly in the JSON
- Include at least 3-5 test cases
- Make tests comprehensive and realistic
- Use appropriate testing framework for the language ({language})

REMEMBER: Output ONLY the JSON object. Start with {{ and end with }}. No other text.
"""
REFACTOR_PROMPT = """You are a senior software engineer specializing in code refactoring and optimization.

Analyze and refactor the following {language} code to improve its quality, readability, and performance.

CODE TO REFACTOR:
```{language}
{code}
```

CRITICAL INSTRUCTIONS:
1. Return ONLY a valid JSON object
2. No markdown code blocks (no ```json or ```)
3. No additional text before or after the JSON
4. Follow the EXACT structure below

REQUIRED JSON STRUCTURE:
{{
  "refactored_code": "// Improved version of the code\\nfunction example() {{\\n  return 'refactored';\\n}}",
  "explanation_of_changes": [
    "Renamed variable 'x' to 'userCount' for better clarity",
    "Extracted duplicate logic into a helper function 'validateInput'",
    "Added error handling for edge cases with try-catch blocks",
    "Improved performance by using a Set instead of Array for lookups"
  ],
  "improvements": [
    "Readability: More descriptive variable and function names",
    "Performance: Reduced time complexity from O(n²) to O(n) by using a hash map",
    "Maintainability: Separated concerns into smaller, focused functions",
    "Error Handling: Added validation and graceful error handling",
    "Best Practices: Follows {language} naming conventions and style guide"
  ],
  "complexity": {{
    "before": {{
      "time": "O(n²) - Nested loops caused quadratic time complexity",
      "space": "O(n) - Linear space for storing results"
    }},
    "after": {{
      "time": "O(n) - Single pass with hash map lookup",
      "space": "O(n) - Maintained linear space complexity"
    }},
    "overall_improvement": "Significant performance improvement for large datasets while maintaining code clarity"
  }}
}}

REFACTORING GUIDELINES:
- Improve variable and function names for clarity
- Extract duplicate code into reusable functions
- Add proper error handling
- Optimize algorithms where possible
- Follow language-specific best practices and conventions
- Add comments for complex logic
- Ensure the refactored code maintains the same functionality
- Use \\n for newlines and escape quotes properly in the JSON

REMEMBER: Output ONLY the JSON object. Start with {{ and end with }}. No other text.
"""