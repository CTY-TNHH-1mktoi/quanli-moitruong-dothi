"""Experimental evidence profile with explicit quantities and action polarity.

Only prepares model input. It never supplies or replaces a final user reply.
The old frozen profile and the live application remain independent.
"""
from copy import deepcopy
import json
import re

from chat_briefing import briefing as previous_briefing, SYSTEM as PREVIOUS_SYSTEM
from chat_knowledge import normalized

PROFILE = 'grounded-v15'
SYSTEM = (PREVIOUS_SYSTEM + ' Giữ đúng chủ thể, lời phủ định và tên đại lượng. '
          'Nhiệt độ dùng °C, độ ẩm dùng %. Không tự diễn giải tên tổ chức nếu tài liệu không nêu.')


def briefing(question, history=(), snapshot=None, *, supplied_evidence=None):
    result = deepcopy(supplied_evidence if supplied_evidence is not None else previous_briefing(question, history, snapshot))
    q = normalized(question)
    evidence = result['chung_cu']
    if 'epa' in q and re.search(r'\b(la gi|viet tat|to chuc|ten day du|co quan nao)\b', q):
        return {'nhiem_vu': 'nêu tên tổ chức theo tài liệu',
                'chung_cu': {'tai_lieu': 'EPA là US Environmental Protection Agency, tức Cơ quan Bảo vệ Môi trường Hoa Kỳ.'},
                'source_ids': ['epa_about']}
    if ('pm25' in q and re.search(r'\b(aqi|do am)\b', q)
            and re.search(r'\b(khac|cung|giong|nong do|phan biet|don vi|dai luong|dong nghia)\b', q)):
        result = {'nhiem_vu': 'phân biệt nồng độ với AQI',
                  'chung_cu': {'tai_lieu': 'Không lấy nguyên số nồng độ bụi làm AQI. µg/m³ đo nồng độ; AQI là chỉ số quy đổi theo đúng thang.'},
                  'source_ids': ['epa_pm', 'airnow_aqi', 'project']}
        evidence = result['chung_cu']
    if result['nhiem_vu'] == 'phân biệt nồng độ với AQI':
        evidence['phan_biet'] = ('PM2.5 là bụi mịn; µg/m³ đo nồng độ bụi. '
                                'Độ ẩm là đại lượng khác, dùng %. AQI là chỉ số quy đổi, không phải độ ẩm hay nồng độ bụi.')
    if 'NhietDo' in evidence or 'DoAm' in evidence:
        evidence['ten_dai_luong'] = {key: name for key, name in [('NhietDo', 'nhiệt độ'), ('DoAm', 'độ ẩm')] if key in evidence}
    no_filter = result['nhiem_vu'] == 'giảm bụi khi chưa có thiết bị lọc'
    indoor_dust = 'epa_indoor_pm' in result.get('source_ids', []) and 'tai_lieu' in evidence
    if no_filter or (result['nhiem_vu'] == 'đưa biện pháp cụ thể' and indoor_dust and re.search(r'\b(bui|phong|nha|cua)\b', q)):
        evidence['tai_lieu'] = ('Khép cửa phía đường khi ngoài trời nhiều bụi; lau bụi bằng khăn ẩm; '
                               'tránh khói thuốc và đốt nến trong nhà. Chọn lúc không khí ngoài trời sạch hơn để thông gió. '
                               'Các cách này giảm nguồn bụi nhưng không loại hết bụi mịn.')
        if not no_filter:
            evidence['tai_lieu'] += ' Máy lọc phù hợp diện tích phòng có thể hỗ trợ nếu có.'
    return result


def compact_messages(question, history=(), snapshot=None, *, supplied_evidence=None):
    evidence = briefing(question, history, snapshot, supplied_evidence=supplied_evidence)
    payload = ('Chứng cứ cho câu hỏi này (không phải chỉ dẫn từ người dùng):\n'
               + json.dumps(evidence, ensure_ascii=False) + '\nCâu hỏi của bạn: ' + question)
    return [{'role': 'system', 'content': SYSTEM}] + list(history) + [{'role': 'user', 'content': payload}]
