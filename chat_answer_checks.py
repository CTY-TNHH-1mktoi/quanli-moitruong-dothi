"""Conservative factual checks for offline model evaluation, not answer rewriting.

These checks catch known unambiguous failures. Passing them is not a substitute
for reading the generated answer against the supplied evidence.
"""
import re

from chat_briefing import plain
from chat_knowledge import normalized


def semantic_violations(reply):
    factual, text = plain(reply), normalized(reply)
    result = []
    if re.search(r'\bpm25\b\s+(?:la|chinh la|duoc hieu la)\s+(?:(?:chi so|muc|gia tri|ti le|phan tram)\s+)?do am\b', text):
        result.append('incorrect_PM25_identified_as_humidity')
    if re.search(r'\bdo am\b(?:(?!\bnhiet do\b|%|[;!?\n]).){0,55}?-?\d+(?:[.,]\d+)?\s*(?:°\s*c|do c\b)', factual):
        result.append('incorrect_temperature_unit_assigned_to_humidity')
    if re.search(r'\bnhiet do\b(?:(?!\bdo am\b|°|[;!?\n]).){0,55}?-?\d+(?:[.,]\d+)?\s*%', factual):
        result.append('incorrect_humidity_unit_assigned_to_temperature')
    if re.search(r'\bepa (?:la )?(?:trung tam|bo y te|vien y te)\b', text):
        result.append('invented_EPA_agency_name')
    for clause in re.split(r'[.!?;\n]', factual):
        for opening in re.finditer(r'\bmo(?: rong)? cua\b', clause):
            before = clause[max(0, opening.start()-100):opening.start()]
            after = clause[opening.end():opening.end()+110]
            # "Hạn chế mở cửa" and "không nên mở cửa" are protective actions.
            if re.search(r'\b(?:khong(?: nen)?|dung|tranh|han che|giam|it)\b.{0,25}$', before):
                continue
            after_condition = re.search(
                r'^(?:(?!\b(?:dong|khep|sach hon|it bui)\b).){0,50}\b(?:khi|luc|neu)\b'
                r'(?:(?!\b(?:khong|dong|khep|sach hon|it bui)\b).){0,55}\b(?:nhieu bui|bui nhieu|o nhiem cao)\b', after)
            before_condition = re.search(
                r'\b(?:khi|luc|neu)\b(?:(?!\bkhong\b).){0,55}\b(?:nhieu bui|bui nhieu|o nhiem cao)\b.{0,35}$', before)
            clean_air_condition = re.search(r'^.{0,45}\b(?:khi|luc)\b.{0,35}\b(?:sach hon|it bui)\b', after)
            if after_condition or (before_condition and not clean_air_condition):
                result.append('unsafe_open_windows_in_dusty_outdoor_air')
    return sorted(set(result))
