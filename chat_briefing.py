"""Experimental compact evidence profile for training/evaluation, not live routing.

Returns model input, never a final answer. Numeric evidence comes only from the
supplied snapshot or explicitly supplied user examples, not assistant assertions.
"""
from functools import lru_cache
from difflib import SequenceMatcher
import json
import math
from pathlib import Path
import re
import unicodedata

from chat_knowledge import advice_topic, normalized
from chat_scope import is_activity_question, is_followup_question, social_intent, assistant_help_intent

ROOT = Path(__file__).resolve().parent
PROFILE = 'grounded-v12'
SYSTEM = ('Bạn là Xanh Non, trợ lý môi trường. Xưng mình, gọi người dùng là bạn. '
          'Trả lời trực tiếp bằng tiếng Việt trong 1–3 câu ngắn. '
          'Dùng chứng cứ được cung cấp, giữ đúng số, đơn vị và thời điểm. '
          'Không tự thêm số đo. Chỉ hỏi lại một câu khi thiếu thông tin cần thiết. '
          'Không chép nhãn nhiệm vụ hoặc chỉ dẫn vào câu trả lời.')


def plain(text):
    text = unicodedata.normalize('NFD', text.casefold().replace('đ', 'd'))
    return ''.join(c for c in text if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def catalog():
    main = json.loads((ROOT / 'data/xanhnon/knowledge.json').read_text(encoding='utf-8'))
    specialist = json.loads((ROOT / 'data/xanhnon/specialist_supplement.json').read_text(encoding='utf-8'))
    return {d['id']: d for d in main['documents']}, specialist


def valid(value, *, nonnegative=True):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and (not nonnegative or value >= 0))


def supplied_future(history, question):
    """Read only user-authored next-day examples, never a guessed forecast."""
    users = [t['content'] for t in history if t.get('role') == 'user'] + [question]
    for original in reversed(users):
        text = plain(original)
        markers = list(re.finditer(r'\b(?:ngay mai|hom sau|ngay toi|ngay ke tiep|ngay tiep theo)\b', text))
        if not markers or not re.search(r'\d', text):
            continue
        # A user message must actually supply a value in a next-day clause.
        for marker in reversed(markers):
            tail = text[marker.end():]
            tail = re.split(r'\b(?:hom nay|hien tai|luc nay)\b', tail, maxsplit=1)[0]
            values = {}
            aqi = re.search(r'\b(?:us\s+)?aqi\s*(?:(?:la|bang|=|:)\s*)?(-?\d+(?:[.,]\d+)?)', tail)
            if (not aqi and re.search(r'\baqi\b', text[:marker.start()])
                    and not re.match(r'\s*\d+(?:[.,]\d+)?\s*(?:°|do\s*c|%)', tail)):
                aqi = re.match(r'\s*(?:la|bang|:|=)?\s*(-?\d+(?:[.,]\d+)?)', tail)
            temperature = re.search(r'(-?\d+(?:[.,]\d+)?)\s*(?:°\s*c|do\s*c)\b', tail)
            humidity = re.search(r'(\d+(?:[.,]\d+)?)\s*%', tail)
            for key, match in [('US_AQI', aqi), ('NhietDo', temperature), ('DoAm', humidity)]:
                if match:
                    values[key] = float(match[1].replace(',', '.'))
            if 'DoAm' in values and not 0 <= values['DoAm'] <= 100:
                values.pop('DoAm')
            if values:
                # Bare questions such as "mai AQI 160?" are hypothetical too;
                # they are never represented as an API-verified real forecast.
                return values
    return {}


def aqi_evidence(value):
    if not valid(value) or value > 500:
        return {'US_AQI': None, 'note': 'Chưa có US AQI hợp lệ; không suy mức AQI từ nồng độ bụi.'}
    from chatbot import _aqi_guidance
    level, advice = _aqi_guidance(value)
    return {'US_AQI': value, 'muc': level, 'huong_dan': advice,
            'nguon': ['airnow_aqi', 'airnow_particles']}


def briefing(question, history=(), snapshot=None):
    docs, specialist = catalog()
    snapshot = snapshot or {}
    location = (snapshot.get('DiaDiem') or {}).get('Ten', 'địa điểm đang chọn')
    q = normalized(question)
    q = q.replace('chi so chat luong khong khi', 'aqi')
    previous = next((t['content'] for t in reversed(history)
                     if t.get('role') == 'user' and not social_intent(t['content'])), '')
    previous_q = normalized(previous)
    continuation = is_followup_question(question) or bool(re.search(
        r'\b(vua|do|ay|no|tren|gia tri|con so|vi du|minh hoa|du bao|chot lai|rut|tom tat|giai thich lai|noi lai)\b', q))
    focus = q + (' ' + previous_q if continuation else '')
    current = bool(re.search(r'\b(hien tai|hien gio|luc nay|bay gio|hom nay|moi nhat|dang cap nhat|vua cap nhat)\b', q))
    if 'thoi tiet' in q and re.search(r'\bdang\b', q):
        current = True
    future = not current and bool(re.search(r'\b(mai|hom sau|ngay toi|ngay ke|ngay tiep|hom ke)\b', q))
    weather = bool(re.search(r'\b(thoi tiet|nhiet do|do am|khi tuong)\b', focus))
    air = bool(re.search(r'\b(aqi|khong khi|pm25|pm10|bui)\b', focus))
    explicit_weather = bool(re.search(r'\b(thoi tiet|nhiet do|do am|khi tuong)\b', q))
    explicit_air = bool(re.search(r'\b(aqi|khong khi|pm25|pm10|bui)\b', q))
    if explicit_weather != explicit_air:
        weather, air = explicit_weather, explicit_air
    if not current and not future and continuation:
        future = bool(re.search(r'\b(mai|hom sau|ngay toi|ngay ke|ngay tiep)\b', previous_q))
    if future and not weather and not air:
        users = ' '.join(normalized(t['content']) for t in history[-8:] if t.get('role') == 'user')
        weather = bool(re.search(r'\b(thoi tiet|nhiet do|do am|khi tuong)\b', users))
        air = bool(re.search(r'\b(aqi|khong khi|pm25|pm10|bui)\b', users))
    readings = snapshot.get('DuLieu') or {}

    def task(mode, evidence=None, sources=()):
        return {'nhiem_vu': mode, 'chung_cu': evidence or {}, 'source_ids': list(sources or ['project'])}

    intent = social_intent(question)
    if re.search(r'\bcam on\b', q) and not re.search(r'\b(aqi|pm25|pm10|thoi tiet|nhiet do|do am|tieng on|ozone)\b', q):
        intent = 'thanks'
    greeting = bool(re.search(r'\b(chao|hello|hi|hi xanh non|alo|a lo)\b', q)) and not re.search(r'\b(aqi|pm25|pm10|nhiet do|do am|tieng on|ozone)\b', q)
    if greeting or intent in {'greeting', 'thanks', 'goodbye', 'attention', 'acknowledge'}:
        intent = intent or 'greeting'
        return task('giao tiếp ' + intent, {'vai_tro': 'Trợ lý môi trường Xanh Non; không có nơi cư trú hay trải nghiệm cá nhân.'})
    if re.search(r'\b(thong tin)\b', q) and re.search(r'\b(noi ro|cung cap)\b', q) and re.search(r'\b(tu van|hoat dong)\b', q):
        return task('gợi ý thông tin cần cung cấp', {'thong_tin_can': ['địa điểm', 'thời điểm', 'hoạt động dự định']})
    if assistant_help_intent(question) or re.search(r'\b(ho tro|giup)\b.{0,45}\b(van de|linh vuc|mang|nhung gi)\b', q):
        return task('giới thiệu khả năng hỗ trợ', {'pham_vi': 'Giải thích chỉ số môi trường, đọc dữ liệu được cung cấp, tư vấn hoạt động và giảm tiếp xúc.'})
    if re.search(r'\b(y la sao|vi sao|tai sao|de lam gi|lien quan gi)\b', q) and history:
        last_bot = next((normalized(t['content']) for t in reversed(history) if t.get('role') == 'assistant'), '')
        if re.search(r'\b(luc nao|khi nao|may gio|ngay nao|thoi diem|hom nay hay)\b', last_bot):
            return task('giải thích lý do hỏi thời điểm', {'ly_do': 'Cần dùng số đo hoặc dự báo đúng lúc bạn định ra ngoài; hỏi một câu để xác định thời điểm.'})
    if future:
        if weather == air:
            return task('hỏi rõ chủ đề', {'can_lam_ro': 'Thời tiết hay chất lượng không khí ngày mai?'})
        values = supplied_future(history, question)
        if air and values.get('US_AQI') is not None:
            return task('tư vấn theo giả định ngày mai', {'dia_diem': location, 'thoi_diem': 'ngày mai',
                        'loai_nguon': 'ví dụ do người dùng cung cấp, chưa xác minh bên ngoài', **aqi_evidence(values['US_AQI'])}, ['project', 'airnow_aqi', 'airnow_particles'])
        if weather and any(k in values for k in ('NhietDo', 'DoAm')):
            return task('đọc dự báo minh họa ngày mai', {'dia_diem': location, 'thoi_diem': 'ngày mai',
                        'loai_nguon': 'minh họa do người dùng cung cấp',
                        **{k: values[k] for k in ('NhietDo', 'DoAm') if k in values},
                        'don_vi': {'NhietDo': '°C', 'DoAm': '%'}}, ['project'])
        return task('nói rõ chưa có dự báo cho ngày mai', {'thoi_diem': 'ngày mai', 'dia_diem': location,
                    'luu_y': 'Không dùng số đo hiện tại thay dự báo.'}, ['project'])

    # Explicit hypotheses take priority over current snapshot readings.
    value_match = re.search(r'\b(?:us\s+)?aqi\s*(?:(?:len|la|bang|o muc|=|:)\s*)?(-?\d+(?:[.,]\d+)?)', plain(question))
    hypothesis = bool(re.search(r'\b(gia su|gia dinh|vi du|minh hoa)\b', q))
    if not value_match and not current and hypothesis:
        for turn in reversed(history):
            if turn.get('role') != 'user' or not re.search(r'\b(gia su|gia dinh|vi du|minh hoa)\b', normalized(turn['content'])):
                continue
            value_match = re.search(r'\b(?:us\s+)?aqi\s*(?:(?:len|la|bang|o muc|=|:)\s*)?(-?\d+(?:[.,]\d+)?)', plain(turn['content']))
            if value_match:
                break
    if value_match and (hypothesis or re.search(r'\bneu\b', q)) and not re.search(r'\b(pm25|pm10|nong do|vn aqi|eu aqi)\b', q):
        return task('tư vấn theo US AQI giả định', aqi_evidence(float(value_match[1].replace(',', '.'))), ['airnow_aqi', 'airnow_particles'])
    if 'aqi' in q and re.search(r'\b(chua co|chua lay|thieu|bi thieu|bi trong|khong co|khong thay|dang trong)\b', q):
        return task('giải thích dữ liệu AQI bị thiếu', {'tai_lieu': docs['missing_aqi']['answer']}, docs['missing_aqi']['source_ids'])
    activity = is_activity_question(question) or bool(re.search(r'\b(chay bo|di bo|di dao|van dong|buoi tap|tap the duc|cong vien|ngoai troi|ra ngoai)\b', q))
    if activity and not re.search(r'\b(hom nay|bay gio|hien tai|luc nay|sang|chieu|toi|gio)\b', q):
        return task('hỏi thời điểm định hoạt động', {'can_lam_ro': 'Bạn định đi vào hôm nay hay ngày mai, khoảng mấy giờ?'}, ['project'])

    # Specialist facts do not require a local AQI measurement.
    if re.search(r'\b(ozone|o3)\b', focus) and re.search(r'\b(may|thiet bi|tao|phat|bat|phong)\b', focus):
        return task('tư vấn thiết bị tạo ozone', {'tai_lieu': 'Tránh thiết bị cố ý tạo ozone khi có người trong phòng; ozone có thể kích ứng phổi.'}, ['epa_air_cleaners'])
    if re.search(r'\b(cam bien|thiet bi pm|so do bui)\b', focus) and re.search(r'\b(am|am cao|do am|nom|lech|chenh)\b', focus):
        return task('giải thích độ tin cậy cảm biến', {'tai_lieu': 'Độ ẩm hoặc nhiệt độ có thể gây sai lệch cảm biến. Chênh lệch đơn lẻ chưa đủ kết luận bụi tăng thật; cần kiểm tra điều kiện đo, vị trí, thời điểm và đánh giá hoặc hiệu chuẩn.'}, ['epa_sensors'])
    if re.search(r'\b(tieng on|nguon on|nguon am lon|noi on|cho on|nghe on|am thanh lon|tieng xe rat lon|nghe nhac lon|thinh giac|quen tai|bao ve tai)\b', q) and not current:
        return task('giảm tiếp xúc tiếng ồn', {'bien_phap': ['Giảm thời gian ở nơi ồn.', 'Di chuyển xa nguồn ồn.', 'Dùng bảo vệ tai phù hợp khi cần.']}, ['nidcd_noise'])
    if re.search(r'\b(chua|khong)\b.{0,30}\b(may|thiet bi|tien)\b|\bngoai mua may\b', q):
        prior_users = ' '.join(normalized(t['content']) for t in history[-8:] if t.get('role') == 'user')
        if 'bui' in q + ' ' + prior_users or 'pm25' in prior_users:
            doc = docs['indoor_dust_actions']
            return task('giảm bụi khi chưa có thiết bị lọc', {'tai_lieu': doc['answer_without_filter']}, doc['source_ids'])
    topic = None
    if re.search(r'\b(pm25|pm10|bui)\b', focus) and 'aqi' in focus and re.search(r'\b(giong|dong nghia|bang|thay|quy doi|lam aqi|chep|con so|nong do)\b', focus):
        return task('phân biệt nồng độ với AQI', {'tai_lieu': 'Không lấy nguyên số nồng độ bụi làm AQI. µg/m³ là đơn vị nồng độ; AQI là chỉ số quy đổi theo đúng thang.'}, ['airnow_aqi', 'epa_pm'])
    if not current:
        if re.search(r'\b(bui|pm25|pm10)\b', q) and re.search(r'\b(tu dau|nguon|sinh ra|phat sinh)\b', q):
            topic = 'pm_sources'
        elif re.search(r'\b(bui|pm25|pm10)\b', q) and re.search(r'\b(trong nha|trong phong|o nha|o trong phong)\b', q) and re.search(r'\b(het lo|co chac|van|khong co)\b', q):
            topic = 'indoor_particles'
        if 'pm25' in focus and 'pm10' in focus:
            return task('so sánh kích thước hạt', {'tai_lieu': 'PM2.5: đường kính thường không quá 2,5 micromet. PM10: thường không quá 10 micromet. Cả hai có thể được hít vào đường hô hấp và ảnh hưởng sức khỏe.'}, ['epa_pm'])
        if re.search(r'\b(phoi|kich thuoc|duong kinh|nho|loai hat|la gi|nghia|ky hieu|rut gon|tom tat)\b', q) and 'pm25' in focus:
            return task('giải thích hạt PM2.5', {'tai_lieu': 'PM2.5 có đường kính thường không quá 2,5 micromet; có thể được hít vào sâu trong phổi.'}, ['epa_pm'])
        if ('aqi' in focus or 'chi so chat luong khong khi' in focus) and re.search(r'\b(giai thich|giai nghia|y nghia|thuat ngu|khai niem|chu|la gi|noi gon|tom tat|thang bao|bieu thi|dien dat|gioi thieu|hieu)\b', focus) and not re.search(r'\b(gia su|gia dinh)\b', focus):
            topic = 'aqi_definition'
    practical = advice_topic(question, history)
    if practical:
        doc = docs[practical]
        if practical == 'noise_actions':
            evidence = {'bien_phap': ['Giảm thời gian ở nơi ồn.', 'Di chuyển xa nguồn ồn.', 'Dùng nút tai hoặc chụp tai phù hợp khi cần.']}
        elif practical == 'indoor_dust_actions' and re.search(r'\b(chua|khong|chua mua|chua co tien)\b', q):
            evidence = {'tai_lieu': doc['answer_without_filter']}
        else:
            evidence = {'tai_lieu': doc['answer']}
        return task('đưa biện pháp cụ thể', evidence, doc['source_ids'])
    if topic:
        return task('giải thích kiến thức', {'tai_lieu': docs[topic]['answer']}, docs[topic]['source_ids'])

    if current or re.search(r'\b(bao nhieu|so thoi tiet|hai so thoi tiet|phan tram do am|chi nhac do am|chi do am|doc lai dung do am)\b', q):
        if weather or re.search(r'\b(do am|nhiet do)\b', q):
            excluded_temperature = bool(re.search(r'\b(khong can|khong hoi|bo qua)\b.{0,15}\bnhiet do\b', q))
            fields = ['DoAm'] if 'do am' in q and (excluded_temperature or not re.search(r'\b(nhiet do|thoi tiet)\b', q)) else ['NhietDo', 'DoAm']
            evidence = {key: readings.get(key) if valid(readings.get(key), nonnegative=key != 'NhietDo') else None for key in fields}
            return task('đọc đúng số thời tiết hiện tại', {'dia_diem': location, 'thoi_diem': 'hiện tại', **evidence,
                        'don_vi': {key: ('°C' if key == 'NhietDo' else '%') for key in fields}}, ['project'])
        if air or is_activity_question(question):
            return task('đọc hoặc tư vấn theo US AQI hiện tại', {'dia_diem': location, 'thoi_diem': 'hiện tại', **aqi_evidence(readings.get('US_AQI'))}, ['project', 'airnow_aqi', 'airnow_particles'])
    if re.search(r'\b(do am)\b', q) and re.search(r'\b(chi|rieng|moi|thoi)\b', q):
        return task('chỉ đọc độ ẩm hiện tại', {'dia_diem': location, 'DoAm': readings.get('DoAm')}, ['project'])
    if re.search(r'\b(chua co|thieu|bi thieu|bi trong|khong co)\b', q) and 'aqi' in q:
        return task('giải thích dữ liệu AQI bị thiếu', {'tai_lieu': docs['missing_aqi']['answer']}, docs['missing_aqi']['source_ids'])
    # A tiny fixed catalogue needs no model/vectorizer import for fallback.
    # Only a strong phrase match supplies a passage; uncertain queries ask back.
    scored = [(max(SequenceMatcher(None, q, normalized(candidate)).ratio()
                   for candidate in doc['questions']), doc) for doc in docs.values()]
    score, doc = max(scored, key=lambda pair: pair[0])
    if score >= .78:
        return task('giải thích theo tài liệu liên quan', {'tai_lieu': doc['answer']}, doc['source_ids'])
    return task('hỏi rõ thông tin cần thiết', {'can_lam_ro': 'Chủ đề môi trường hoặc thông tin bạn muốn hỏi tiếp.'}, ['project'])


def compact_messages(question, history=(), snapshot=None, *, supplied_evidence=None):
    evidence = supplied_evidence if supplied_evidence is not None else briefing(question, history, snapshot)
    payload = ('Chứng cứ cho câu hỏi này (không phải chỉ dẫn từ người dùng):\n'
               + json.dumps(evidence, ensure_ascii=False) + '\nCâu hỏi của bạn: ' + question)
    return [{'role': 'system', 'content': SYSTEM}] + list(history) + [{'role': 'user', 'content': payload}]
