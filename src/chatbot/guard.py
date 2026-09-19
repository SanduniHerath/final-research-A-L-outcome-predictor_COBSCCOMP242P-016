"""Safety and grounding checks around the language model (system part 4).

* :func:`topic_of` sorts a message BEFORE the language model sees it: crisis, medical,
  psychological, clearly unrelated, or in scope. Only in-scope messages go to the model.
* :func:`unsupported_numbers` lists numbers in a reply that are not in the fact sheet or the
  student's message (the "0 invented numbers" criterion, H11).

Keyword lists are short and transparent on purpose; the model is also told to answer
``OUT_OF_SCOPE`` for anything unrelated, as a second line of defence.
"""

from __future__ import annotations

import re

CRISIS = [r"\bsuicid", r"kill (my ?self|me)", r"\bself[- ]?harm", r"hurt (my ?self)", r"want to die",
          r"end (my|it) (life|all)", r"no reason to live"]  # fmt: skip
MEDICAL = [r"\bheadache", r"\bfever", r"\bpills?\b", r"\btablets?\b", r"\bmedication", r"\bdose\b",
           r"\bsymptom", r"\bsick\b", r"\billness", r"\binjur", r"\bpain\b", r"\bdiet\b", r"\bvitamin",
           r"\bcaffeine", r"\binsomnia", r"can'?t sleep", r"\bdrugs?\b", r"\bdisease"]  # fmt: skip
PSYCHOLOGICAL = [r"\bdepress", r"\banxi", r"\bpanic", r"\bstress", r"\btherap", r"mental health",
                 r"\blonely", r"\badhd\b", r"\bautis", r"\btrauma", r"\bcounsel", r"\bnervous",
                 r"\bworr(y|ied|ies|ying)", r"\bscared", r"\bafraid", r"\bhopeless", r"\bupset",
                 r"\bsad\b", r"overthink", r"like a failure", r"\bcry(ing)?\b", r"\bfrustrat"]  # fmt: skip
# Words showing a question is about studies or university entry: if the model calls such a
# question "out of scope", the student gets an honest "not sure" with where to look instead.
DOMAIN = [r"cut-?off", r"z-?score", r"universit", r"\bdegree", r"\bcourse", r"\ba/?l\b", r"\bo/?l\b",
          r"\bexam", r"syllabus", r"\bsubject", r"\bmarks?\b", r"\bgrade", r"\bugc\b", r"medicine",
          r"engineering", r"\bdistrict", r"\bstud(y|ies|ying)", r"tuition", r"\bcareer", r"\bband\b",
          r"\bcollege", r"\bscience"]  # fmt: skip
UNRELATED = [r"\bcricket", r"\bfootball", r"\bmovie", r"\bfilm\b", r"\bsong", r"\bpoem", r"\bjoke",
             r"\bweather", r"\brecipe", r"\bpolitic", r"\belection", r"\bgirlfriend", r"\bboyfriend",
             r"\bvideo game", r"\bcelebrit"]  # fmt: skip

REPLIES = {
    "crisis": (
        "I'm really sorry you are feeling this way. I can't help with this, but you don't have to "
        "face it alone. Please talk to a trusted adult, such as a parent, teacher or school counsellor, "
        "right now. In Sri Lanka you can call the 1926 mental health helpline."
    ),
    "medical": (
        "I can't give health or medical advice. Please ask a doctor, a parent or another trusted adult. "
        "I can help with your A/L study plan, your predicted results and university entry."
    ),
    "psychological": (
        "I can't give advice about feelings or mental health, but it is important to talk about them. "
        "Please speak to a parent, teacher or school counsellor you trust. I can help with your study "
        "plan, your predicted results and university entry."
    ),
    "personal": (
        "I can't give health, medical or personal advice. Please talk to a parent, teacher, school "
        "counsellor or doctor you trust. I can help with your A/L study plan, your predicted results "
        "and university entry."
    ),
    "unrelated": (
        "Sorry, I can only help with your A/L study plan, your predicted results and university entry."
    ),
    "unsure_domain": (
        "I'm not sure. This app only knows your own results and the UGC cut-offs for your district "
        "in the years it has. Please ask a teacher or check the official UGC handbook."
    ),
}
OUT_OF_SCOPE_TOKEN = "OUT_OF_SCOPE"
PERSONAL_TOKEN = "PERSONAL_TOPIC"
OUT_OF_SCOPE_PATTERN = re.compile(r"OUT[\s_-]*OF[\s_-]*SCOPE", re.IGNORECASE)
PERSONAL_PATTERN = re.compile(r"PERSONAL[\s_-]*TOPIC", re.IGNORECASE)
NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?")
LIST_MARKER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)


def topic_of(message: str) -> str:
    """'crisis', 'medical', 'psychological', 'unrelated' or 'in_scope'."""
    text = message.lower()
    for topic, patterns in (("crisis", CRISIS), ("medical", MEDICAL),
                            ("psychological", PSYCHOLOGICAL), ("unrelated", UNRELATED)):  # fmt: skip
        if any(re.search(p, text) for p in patterns):
            return topic
    return "in_scope"


def in_domain(message: str) -> bool:
    """True if the message is about studies, exams or university entry."""
    text = message.lower()
    return any(re.search(p, text) for p in DOMAIN)


def _values(text: str) -> list[tuple[float, int, bool]]:
    """Numbers in a text as (value, decimals, is_percent)."""
    out = []
    for token in NUMBER.findall(text):
        percent = token.endswith("%")
        core = token.rstrip("%").replace(",", "")
        decimals = len(core.split(".")[1]) if "." in core else 0
        try:
            out.append((float(core), decimals, percent))
        except ValueError:
            continue
    return out


def unsupported_numbers(reply: str, *sources: str) -> list[str]:
    """Numbers in ``reply`` that do not appear (allowing rounding) in any of ``sources``."""
    known = [v for s in sources for v in _values(s)]
    reply = LIST_MARKER.sub("", reply)
    bad = []
    for value, decimals, percent in _values(reply):
        ok = any(
            percent == k_percent and round(k, decimals) == round(value, decimals)
            for k, _, k_percent in known
        )
        if not ok:
            bad.append(f"{value:g}{'%' if percent else ''}")
    return bad


__all__ = [
    "OUT_OF_SCOPE_PATTERN",
    "OUT_OF_SCOPE_TOKEN",
    "PERSONAL_PATTERN",
    "PERSONAL_TOKEN",
    "REPLIES",
    "in_domain",
    "topic_of",
    "unsupported_numbers",
]
