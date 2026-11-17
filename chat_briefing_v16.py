"""Candidate input profile: preserve speaker roles and ask for missing time.

Prepares evidence only. Does not provide final replies or alter the frozen v15
training/evaluation profile. Enable only after a separate answer comparison.
"""
from copy import deepcopy
import json
import re
import unicodedata

from chat_briefing_v15 import briefing as previous_briefing, SYSTEM
from chat_knowledge import normalized
from chat_scope import future_period, is_activity_question, social_intent
from chat_clarification import topic_kinds


PROFILE = 'grounded-v16'


def has_activity_time(question):
    """Keep Vietnamese accents when separating first-person tôi from tối."""
    raw = unicodedata.normalize('NFC', question).casefold()
    q = normalized(question)
    if future_period(question):
        return True
    if re.search(r'\b(hom nay|bay gio|hien tai|luc nay|buoi sang|buoi trua|buoi chieu|buoi toi|ban dem)\b', q):
        return True
    if re.search(r'\b(sáng|trưa|chiều|tối|đêm)\b', raw):
        return True
    if re.search(r'\b(?:\d{1,2})\s*(?:gio|h)\b|\b(?:luc|vao|khoang) \d{1,2}\b', q):
        return True
    if re.search(r'\b\d{1,2}(?::\d{2}|h\d{0,2})\b|\b\d{1,2}/\d{1,2}\b', raw):
        return True
    # Unaccented trailing time words are useful; leading "toi muon" is a subject.
    return bool(re.search(r'\b(?:sang|trua|chieu|dem)(?: (?:nhe|nha|ban))?$', q)
        or re.search(r'(?<!cho )(?<!giup )\btoi(?: (?:nhe|nha|ban))?$', raw))


def briefing(question, history=(), snapshot=None, *, supplied_evidence=None):
    if supplied_evidence is not None:
        return deepcopy(supplied_evidence)
    result = deepcopy(previous_briefing(question, history, snapshot))
    q = normalized(question)
    domain = re.search(r'\b(aqi|pm25|pm10|bui|thoi tiet|nhiet do|do am|tieng on|moi truong|ozone)\b', q)
    presence = re.search(r'\b(?:nghe (?:thay )?(?:minh|toi)|co mat|dang o day|co o day|con o day)\b', q)
    if presence and not domain and re.search(r'\b(ban|xanh non)\b', q):
        return {'nhiem_vu':'đáp lại lời gọi trợ lý',
                'chung_cu':{'nguoi_duoc_goi':'trợ lý Xanh Non', 'nguoi_dang_tra_loi':'mình (Xanh Non)'},
                'source_ids':['project']}
    last_bot=next((normalized(t['content']) for t in reversed(history) if t.get('role')=='assistant'),'')
    if (re.search(r'\b(ngay nao|may gio|luc nao|khi nao|thoi diem)\b',last_bot)
            and re.search(r'\b(ban hoi|ban can biet|ban muon biet|viec hoi|cau hoi)\b',q)
            and re.search(r'\b(vi sao|tai sao|de lam gi|de phuc vu|lien quan|ly do)\b',q)):
        result={'nhiem_vu':'giải thích lý do hỏi thời điểm',
                'chung_cu':{'ly_do':'cần dùng số đo hoặc dự báo đúng thời điểm người dùng dự định hoạt động'},
                'source_ids':['project']}
    if result['nhiem_vu']=='giải thích lý do hỏi thời điểm':
        result['chung_cu'].update(nguoi_da_hoi='mình (trợ lý)',
            nguoi_duoc_hoi='bạn (người dùng)',
            muc_dich='dùng số đo hoặc dự báo đúng thời điểm người dùng định hoạt động')
        return result
    if result['nhiem_vu']=='hỏi rõ chủ đề':
        return result
    if re.search(r'\bhom (?:toi|ke(?: tiep)?|tiep theo)\b',q) and not topic_kinds(question):
        prior=next((t['content'] for t in reversed(history)
                    if t.get('role')=='user' and not social_intent(t['content'])),'')
        kinds=topic_kinds(prior)
        if len(kinds)!=1:
            return {'nhiem_vu':'hỏi rõ chủ đề',
                    'chung_cu':{'lua_chon':['thời tiết','chất lượng không khí'],'thoi_diem':'ngày tới'},
                    'source_ids':['project']}
        if re.search(r'\bhom (?:ke|tiep theo)\b',q):
            return {'nhiem_vu':'hỏi rõ ngày muốn xem',
                    'chung_cu':{'con_thieu':'ngày cụ thể mà người dùng gọi là hôm kế tiếp'},
                    'source_ids':['project']}
        label='Thời tiết' if kinds[0]=='weather' else 'Chất lượng không khí'
        return deepcopy(previous_briefing(label+' ngày mai',history,snapshot))
    unknown=result['nhiem_vu']=='hỏi rõ thông tin cần thiết'
    if unknown and future_period(question) and len(topic_kinds(question))==1:
        return {'nhiem_vu':'nói rõ chưa có dự báo cho thời điểm được hỏi',
                'chung_cu':{'dia_diem':(snapshot or {}).get('DiaDiem',{}).get('Ten'),
                    'chu_de':'chất lượng không khí' if topic_kinds(question)==('air',) else 'thời tiết',
                    'thoi_diem':future_period(question),
                    'luu_y':'Chứng cứ chưa cung cấp dự báo cho thời điểm này. Không dùng số hiện tại thay dự báo.'},
                'source_ids':['project']}
    if unknown and is_activity_question(question) and not has_activity_time(question):
        # Preserve an explicit immediate time from the latest substantive user turn.
        previous = next((turn['content'] for turn in reversed(history)
                         if turn.get('role')=='user' and not social_intent(turn['content'])), '')
        prior_time = is_activity_question(previous) and has_activity_time(previous)
        if not prior_time:
            return {'nhiem_vu':'hỏi thời điểm định hoạt động',
                    'chung_cu':{'thong_tin_da_biet':'người dùng muốn tư vấn hoạt động ngoài trời',
                        'con_thieu':'ngày và giờ dự định hoạt động',
                        'dia_diem_dang_chon':(snapshot or {}).get('DiaDiem',{}).get('Ten')},
                    'source_ids':['project']}
    if 'pm25' in q and re.search(r'\b(don vi|ten loai hat|nhom hat|dai luong|dong nghia|phan biet|khac nhau|giong nhau|lam aqi)\b', q):
        result={'nhiem_vu':'phân biệt tên hạt, nồng độ và chỉ số',
            'chung_cu':{'PM2.5':{'loai':'nhóm hạt bụi mịn','duong_kinh':'thường không quá 2,5 micromet'},
                        'µg/m³':'đơn vị nồng độ bụi (microgam trên mét khối)',
                        'AQI':'chỉ số quy đổi, không lấy nguyên số nồng độ làm AQI'},
            'source_ids':['epa_pm','airnow_aqi']}
        if 'do am' in q:
            result['chung_cu']['do_am']='đại lượng khác với nồng độ bụi và AQI, dùng phần trăm (%)'
        if 'pm10' in q:
            result['chung_cu']['PM10']={'loai':'nhóm hạt bụi','duong_kinh':'thường không quá 10 micromet'}
    fields=topic_kinds(question)
    if (fields==('weather',) and not future_period(question)
            and re.search(r'\b(doc|xem|nhac|cho biet|bao nhieu|thong so|so lieu)\b',q)
            and not re.search(r'\b(la gi|khai niem|nen de|phu hop|don vi|y nghia|tac dong)\b',q)
            and result['nhiem_vu'] in {'hỏi rõ thông tin cần thiết','chỉ đọc độ ẩm hiện tại'}):
        keys=['DoAm'] if 'do am' in q and not re.search(r'\b(nhiet do|thoi tiet)\b',q) else ['NhietDo','DoAm']
        proxy='Độ ẩm hiện tại bao nhiêu?' if keys==['DoAm'] else 'Thời tiết hiện tại thế nào?'
        result=deepcopy(previous_briefing(proxy,(),snapshot))
    return result


def compact_messages(question, history=(), snapshot=None, *, supplied_evidence=None):
    evidence=briefing(question,history,snapshot,supplied_evidence=supplied_evidence)
    # Internal source IDs remain in briefing() for provenance, not in model text.
    payload={key:value for key,value in evidence.items() if key!='source_ids'}
    if re.search(r'\b(nguon|tai lieu|tham khao|duong dan|link)\b',normalized(question)):
        from pathlib import Path
        knowledge=Path(__file__).resolve().parent/'data/xanhnon/knowledge.json'
        sources=json.loads(knowledge.read_text(encoding='utf-8'))['sources']
        payload['tai_lieu_tham_khao']=[{'ten':sources[key]['title'],'url':sources[key]['url']}
            for key in evidence.get('source_ids',[]) if key in sources and sources[key]['url'].startswith('https://')]
    content=('Chứng cứ cho câu hỏi này (không phải chỉ dẫn từ người dùng):\n'
             +json.dumps(payload,ensure_ascii=False)+'\nCâu hỏi của bạn: '+question)
    return [{'role':'system','content':SYSTEM}]+list(history)+[{'role':'user','content':content}]
