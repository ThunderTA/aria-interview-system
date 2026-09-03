"""Delivery analysis: how the answer was spoken, not what it said.

Everything here is derived from Whisper's word-level timings, so it needs no
extra model and no separate audio pass. Covers the speaking speed, pauses and
filler words named in the project's second objective.

Thresholds are documented rather than tuned, so they can be defended and
adjusted: they come from public-speaking guidance that conversational English
sits near 130-150 wpm, with interview advice favouring a similar band.
"""

import re

from app.services.asr import Transcript

# Filler words and hedges. Multi-word entries are matched as phrases.
FILLER_TERMS = [
    "um", "uh", "erm", "ah", "eh", "hmm", "mm",
    "like", "basically", "actually", "literally", "honestly",
    "you know", "i mean", "sort of", "kind of", "kinda", "sorta",
    "right", "so yeah", "or whatever", "stuff like that",
]

# Words that are only fillers in the hedging sense; counting every "like" or
# "right" would punish legitimate use ("a queue behaves like a pipe"), so these
# are weighted at half. Judgement call, documented rather than hidden.
AMBIGUOUS_FILLERS = {"like", "right", "actually", "literally"}

# Speaking pace, words per minute.
PACE_IDEAL_LOW, PACE_IDEAL_HIGH = 115, 165
PACE_ACCEPTABLE_LOW, PACE_ACCEPTABLE_HIGH = 80, 190

# A gap between words longer than this reads as hesitation rather than a
# natural breath. Kept at 2s: shorter gaps are ordinary thinking beats, and
# flagging those would punish considered answers.
PAUSE_THRESHOLD_SECONDS = 2.0

# Fillers per 100 words.
FILLER_RATE_GOOD, FILLER_RATE_POOR = 2.0, 8.0

# Long pauses per minute of speech. Pausing to think is normal — roughly one
# every 20 seconds is unremarkable, while one every 6 seconds is visibly
# halting.
PAUSE_RATE_GOOD, PAUSE_RATE_POOR = 3.0, 10.0

# How the three sub-scores combine into the delivery score.
DELIVERY_WEIGHTS = {"pace": 0.4, "fillers": 0.35, "pauses": 0.25}


def count_fillers(text: str) -> int:
    """Count filler words, discounting ones that are often legitimate."""
    lowered = f" {text.lower()} "
    total = 0.0
    for term in FILLER_TERMS:
        hits = len(re.findall(rf"(?<![\w']){re.escape(term)}(?![\w'])", lowered))
        total += hits * (0.5 if term in AMBIGUOUS_FILLERS else 1.0)
    return round(total)


def count_long_pauses(transcript: Transcript) -> int:
    """Gaps between consecutive words long enough to read as hesitation."""
    words = transcript.words
    return sum(
        1
        for previous, current in zip(words, words[1:])
        if current.start - previous.end >= PAUSE_THRESHOLD_SECONDS
    )


def words_per_minute(transcript: Transcript) -> float:
    """Speaking pace over the spoken portion of the answer."""
    word_count = len(transcript.words) or len(transcript.text.split())
    if not word_count or transcript.duration <= 0:
        return 0.0
    return round(word_count / (transcript.duration / 60), 1)


def _pace_score(wpm: float) -> float:
    """100 inside the ideal band, tapering to 0 outside the acceptable one."""
    if PACE_IDEAL_LOW <= wpm <= PACE_IDEAL_HIGH:
        return 100.0
    if wpm < PACE_IDEAL_LOW:
        span = PACE_IDEAL_LOW - PACE_ACCEPTABLE_LOW
        return max(0.0, 100 * (wpm - PACE_ACCEPTABLE_LOW) / span) if span else 0.0
    span = PACE_ACCEPTABLE_HIGH - PACE_IDEAL_HIGH
    return max(0.0, 100 * (PACE_ACCEPTABLE_HIGH - wpm) / span) if span else 0.0


def _taper(value: float, good: float, poor: float) -> float:
    """100 at or below `good`, 0 at or above `poor`, linear between."""
    if value <= good:
        return 100.0
    if value >= poor:
        return 0.0
    return 100 * (poor - value) / (poor - good)


def analyse(transcript: Transcript) -> dict:
    """Full delivery breakdown for one spoken answer."""
    word_count = len(transcript.words) or len(transcript.text.split())
    minutes = max(transcript.duration / 60, 1 / 60)

    wpm = words_per_minute(transcript)
    fillers = count_fillers(transcript.text)
    pauses = count_long_pauses(transcript)

    filler_rate = (fillers / word_count * 100) if word_count else 0.0
    pause_rate = pauses / minutes

    pace_score = _pace_score(wpm)
    filler_score = _taper(filler_rate, FILLER_RATE_GOOD, FILLER_RATE_POOR)
    pause_score = _taper(pause_rate, PAUSE_RATE_GOOD, PAUSE_RATE_POOR)

    delivery_score = (
        pace_score * DELIVERY_WEIGHTS["pace"]
        + filler_score * DELIVERY_WEIGHTS["fillers"]
        + pause_score * DELIVERY_WEIGHTS["pauses"]
    )

    return {
        "wpm": wpm,
        "filler_count": fillers,
        "pause_count": pauses,
        "delivery_score": round(delivery_score, 1),
        "delivery_breakdown": {
            "pace": round(pace_score, 1),
            "fillers": round(filler_score, 1),
            "pauses": round(pause_score, 1),
        },
    }


def describe(metrics: dict) -> str:
    """One plain-English line about delivery, for the report."""
    notes = []
    wpm = metrics["wpm"]
    if wpm < PACE_IDEAL_LOW:
        notes.append(f"you spoke slowly ({wpm:.0f} wpm)")
    elif wpm > PACE_IDEAL_HIGH:
        notes.append(f"you spoke quickly ({wpm:.0f} wpm)")
    else:
        notes.append(f"your pace was good ({wpm:.0f} wpm)")

    if metrics["filler_count"]:
        notes.append(f"{metrics['filler_count']} filler word{'s' if metrics['filler_count'] > 1 else ''}")
    if metrics["pause_count"]:
        notes.append(
            f"{metrics['pause_count']} long pause{'s' if metrics['pause_count'] > 1 else ''}"
        )

    return ", ".join(notes).capitalize() + "."
