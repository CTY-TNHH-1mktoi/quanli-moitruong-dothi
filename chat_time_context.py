"""Keep explicit clock times separate from dates and numeric measurements."""
import re
import unicodedata


_CLOCK = re.compile(r'\b(?:(\d{1,2})\s*(?:h|gi[oờ])(?:\s*(\d{1,2}))?|(\d{1,2}):(\d{2}))\b',re.I)


def _plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.casefold()) if not unicodedata.combining(c))


def _match(text):
    raw=_plain(text)
    match=_CLOCK.search(raw)
    if match and not re.match(r'\s*nua\b',raw[match.end():]):
        return match
    return None


def explicit_clock(text):
    match=_match(text)
    if not match:
        return None
    hour=int(match[1] if match[1] is not None else match[3])
    minute=int((match[2] or '0') if match[1] is not None else match[4])
    return (hour,minute) if 0<=hour<24 and 0<=minute<60 else None


def invalid_clock(text):
    return _match(text) is not None and explicit_clock(text) is None


def without_clock(text):
    raw=_plain(text)
    match=_match(text)
    return raw[:match.start()]+' '+raw[match.end():] if match else text


def clock_label(clock):
    return f'{clock[0]:02d}:{clock[1]:02d}'
