import re

TEMPLATES = [
    "He didn’t expect THIS…",
    "This took a wild turn👇",
    "No way this just happened…",
    "Wait for it…",
    "I can’t believe he said that",
]

def make_hook(transcript: str) -> str:
    t = transcript.strip()
    # Use first question as hook if present
    m = re.search(r'([^?]{5,}\?)', t[:200])
    if m:
        q = m.group(1).strip()
        if len(q) <= 80:
            return q
    # Use emphatic sentence
    for key in ["no way", "what the", "bro", "omg", "dude", "insane", "unbelievable"]:
        if key in t.lower():
            return "No way—watch this!"
    # Fallback template
    return TEMPLATES[0]
