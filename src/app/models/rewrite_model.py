from functools import lru_cache

from language_tool_python import LanguageToolPublicAPI
from language_tool_python.utils import correct


@lru_cache(maxsize=1)
def get_tool():
    return LanguageToolPublicAPI('en-US')

def correct_text(text: str) -> dict:
    try:
        tool = get_tool()
        matches = tool.check(text)
        return {
            "corrected": correct(text, matches),
            "matches": [m.ruleId for m in matches],
        }
    except Exception as e:
        # fallback: no crash, just return the original text
        return {
            "corrected": text,
            "matches": [],
            "error": str(e),
        }
