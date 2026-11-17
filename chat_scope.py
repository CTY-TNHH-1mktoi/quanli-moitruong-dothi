"""Recognize environmental topics and conversation intents."""

import re

from chat_knowledge import is_known_question, normalized, filter_constraint_followup


# Kept for reading legacy conversation fixtures; live replies no longer use it.
OUT_OF_SCOPE_REPLY = "Chào, tôi là chat bot môi trường xanh non tôi có thể giúp gì cho bạn"

_ENVIRONMENT = re.compile(
    r"\b(aqi|us aqi|vn aqi|pm25|pm2 5|pm10|pm1|no2|so2|co2|o3|ozone|voc|carbon monoxide|"
    r"carbon monoxit|nong do co|chi so co|co la gi|"
    r"moi truong|o nhiem|khong khi|chat luong nuoc|nguon nuoc|nuoc thai|nuoc sach|"
    r"nuoc ngam|nuoc mat|bui|khoi bui|khoi thai|khi thai|phat thai|khi nha kinh|"
    r"carbon|cac bon|bien doi khi hau|khi hau|he sinh thai|da dang sinh hoc|"
    r"rac|chat thai|tai che|song xanh|cay xanh|trong cay|quang hop|bao ve rung|pha rung|"
    r"hieu ung nha kinh|tiet kiem nang luong|nang luong tai tao|"
    r"tiet kiem dien|tiet kiem nuoc|tui nilon|nhua dung mot lan|"
    r"tieng on|do on|dba|decibel|deciben|bao ve tai|nut tai|chup tai|loa lon|loa to|noi on|cho on|nguon on|am thanh lon|tieng lon|quen tai|"
    r"nom am|am moc|nam moc|am thap|am qua|on qua|cadr|"
    r"thoi tiet|nhiet do|bao nhieu do|do am|du bao thoi tiet|troi mua|mua lon|mua axit|"
    r"luong mua|co mua khong|troi nang|nang nong|tia uv|tia tu ngoai|"
    r"toc do gio|huong gio|gio manh|gio lon|con bao|gio bao|co bao|bao lon|"
    r"suong mu|ngap lut|han han|thien tai|"
    r"may loc khong khi|loc bui|hepa|khau trang|nhom nhay cam|"
    r"cam bien moi truong|tram quan trac|quan trac|giam sat moi truong|"
    r"bang giam sat|bang dieu khien|du lieu giam sat|du lieu moi truong|"
    r"cap nhat du lieu|dia diem dang chon|dia diem duoc chon|"
    r"air quality|air pollution|environment|particulate|fine dust|pollution|"
    r"recycling|wastewater|climate change|weather|humidity|temperature)\b"
)
_OUTDOOR = re.compile(
    r"\b(co nen|nen|co the|co can han che)\b.{0,40}\b(ra ngoai|ngoai troi|di dao|chay bo|tap the duc|dap xe)\b"
    r"|\b(ra ngoai|ngoai troi|di dao|chay bo|tap the duc|dap xe)\b.{0,30}\b(duoc khong|duoc ko|dc ko|co an toan|on khong)\b"
)
_VIETNAMESE_WEATHER = re.compile(r"\b(mưa|bão|gió|nắng)\b", re.IGNORECASE)
_PHYSICAL_ACTIVITY = re.compile(
    r"\b(ra ngoai|ngoai troi|di dao|di bo|tan bo|chay bo|dap xe|tap the duc|"
    r"da ngoai|picnic|choi the thao|di choi|ra san)\b"
)
_OTHER_ACTIVITY_TOPIC = re.compile(
    r"\b(kinh doanh|dau tu|chung khoan|bitcoin|tien ao|python|viet code|lap trinh|"
    r"nau an|nau mon|world cup|cau lac bo|dien thoai|may giat|ngan hang)\b"
)


def _intent_text(message):
    return expand_shorthand(normalized(message))


def expand_shorthand(question):
    for shorthand, expanded in [(r"\b(?:ko|khum|hok|k)\b", "khong"),
                                (r"\bdc\b", "duoc"), (r"\bhnay\b", "hom nay"),
                                (r"\b(?:bh|bg)\b", "bay gio"), (r"\bclkk\b", "chat luong khong khi"),
                                (r"\b(?:tnao|tn|ntn)\b", "the nao"), (r"\bbnh\b", "bao nhieu")]:
        question = re.sub(shorthand, expanded, question)
    return question


_FUTURE_TIME = (
    r"(?:ngay kia|(?:(?:sang|trua|chieu|toi|dem) )?(?:ngay )?mai|"
    r"(?:sang|trua|chieu|toi|dem) nay|cuoi tuan(?: nay| toi)?|"
    r"(?:ngay|tuan|thang|nam) (?:sau|toi)|"
    r"(?:mot|hai|ba|\d+) (?:gio|phut|ngay) nua|sap toi)"
)


def future_period(message):
    """Recognize relative forecast times, including the casual bare 'mai'."""
    question = _intent_text(message)
    # 'Cây mai' and 'hoa mai' name a plant, not tomorrow.
    question = re.sub(r"\b(?:cay|hoa) mai\b", "", question)
    match = re.search(r"\b" + _FUTURE_TIME + r"\b", question)
    if not match:
        from chat_time_context import explicit_clock
        if explicit_clock(message) and re.search(r'\bhom nay\b',question):
            return 'hôm nay'
        return "sắp tới" if re.search(r"\bdu bao\b", question) else None
    period = match[0]
    if period in {"mai", "ngay mai"}:
        return "ngày mai"
    words = {"ngay": "ngày", "kia": "kia", "sang": "sáng", "trua": "trưa",
             "chieu": "chiều", "toi": "tối", "dem": "đêm", "nay": "nay",
             "cuoi": "cuối", "tuan": "tuần", "thang": "tháng", "nam": "năm",
             "sau": "sau", "mot": "một", "hai": "hai", "ba": "ba",
             "gio": "giờ", "phut": "phút", "nua": "nữa", "sap": "sắp"}
    tokens = period.split()
    result = [words.get(word, word) for word in tokens]
    # 'tới' and the time of day 'tối' share the same accent-free spelling.
    if tokens[-1] == "toi" and tokens[-2] in {"ngay", "tuan", "thang", "nam", "sap"}:
        result[-1] = "tới"
    return " ".join(result)


def is_helpful_message(message):
    return bool(re.fullmatch(
        r"(?:(?:cau tra loi|thong tin)(?: nay| do| vua roi)? (?:rat )?|rat )?huu ich"
        r"(?: (?:lam|that|qua|luon|day|do|nhe|a|cam on|cam on ban))*", _intent_text(message)))


def social_intent(message):
    """Match a whole social turn; greetings must not swallow a real question."""
    question = _intent_text(message)
    if is_helpful_message(message):
        return "thanks"
    question = re.sub(r"(?: (?:nhe|nhi|a|nha|nhe ban|ban|xanh non|ban oi|nhe xanh non))+$", "", question)
    if re.fullmatch(r"(?:xin chao|chao|hello|hi|helo|alo|hey)(?: (?:ban|xanh non|bot))?", question):
        return "greeting"
    if re.fullmatch(r"(?:cam on|cam on nhieu|cam on ban nhieu|thank you|thanks|thank|tks|thx|da cam on|minh cam on|toi cam on)", question):
        return "thanks"
    if re.fullmatch(r"(?:tam biet|chao tam biet|hen gap lai|bye|goodbye)", question):
        return "goodbye"
    if re.fullmatch(r"(?:ok|oke|okay|oki|duoc|duoc roi|hieu roi|minh hieu roi|toi hieu roi|ro roi|da|vang|uh|um|u)", question):
        return "acknowledge"
    if re.fullmatch(r"(?:ban (?:oi|co do khong|con do khong)|xanh non (?:oi|co do khong)|co ai khong)", question):
        return "attention"
    # Accept ordinary attention checks while keeping substantive requests intact.
    attention_words=set('xanh non ban tro ly toi minh oi co con dang van o day do mat nghe thay noi nay gio bay cau hoi cho chut mot luc nhe nha a chu khong ko duoc vui long alo hay tra loi giup'.split())
    if (set(question.split()) <= attention_words
            and re.search(r'\b(ban|xanh non|tro ly)\b',question)
            and re.search(r'\b(nghe|o day|co mat|co do|con do)\b',question)):
        return 'attention'
    if re.fullmatch(r"(?:(?:minh|toi) )?(?:chua hieu|khong hieu|chua ro)(?: (?:lam|y ban))?|y (?:ban )?la sao", question):
        return "clarify"
    if re.fullmatch(r"(?:ban (?:noi|tra loi) (?:sai|nham) roi|khong dung roi|sai roi)", question):
        return "correction"
    if re.fullmatch(r"(?:(?:minh|toi) can )?tu van(?: (?:giup|cho) (?:minh|toi))?|giup (?:minh|toi)(?: voi)?", question):
        return "help"
    return None


def current_time_reply(message):
    """A whole conversational reply giving the present time, not a new topic."""
    question = _intent_text(message)
    question = re.sub(r"(?: (?:luon|nhe|nha|a|ban|nhi))+$", "", question)
    question = re.sub(r"^(?:(?:the|vay|con|ngay) )+", "", question)
    question = re.sub(r" thi sao$", "", question)
    return question in {"bay gio", "hien tai", "hom nay", "luc nay", "gio"}


def is_time_followup(message):
    """A time-only conversational turn can inherit a topic, never a new subject."""
    from chat_time_context import explicit_clock,without_clock
    has_clock=explicit_clock(message) is not None
    question = _intent_text(without_clock(message) if has_clock else message)
    if has_clock:
        question=re.sub(r'\b(?:luc|vao|khoang)\b',' ',question)
        question=re.sub(r'\b(?:doi sang|chuyen sang|doi lai|xem lai)\b',' ',question)
        question=' '.join(question.split())
        if re.fullmatch(r'(?:(?:thi sao|the nao|ra sao|the|vay|con|nhe|nhi|ban|a|xem|giup minh|giup toi)\s*)*',question):
            return True
    prefix = (r"(?:(?:the|vay|con|ban|ban oi|hay|xem|thu|tu van|goi y|"
              r"giup (?:minh|toi)|cho (?:minh|toi)(?: (?:hoi|biet))?) )*")
    period = r"(?:" + _FUTURE_TIME + r"|hom nay|bay gio|hien tai|luc nay|gio)"
    suffix = (r"(?: (?:thi )?(?:sao|the nao|ra sao|co tot hon khong|co xau hon khong))?"
              r"(?: (?:nhe|nhi|voi|ban|a|di|luon|duoc khong))*")
    return bool(re.fullmatch(prefix + period + suffix, question))


def strip_time_references(message):
    """Replace the old time when resolving a follow-up instead of joining dates."""
    question = _intent_text(message)
    period = r"(?:" + _FUTURE_TIME + r"|hom nay|bay gio|hien tai|luc nay|hien gio)"
    return ' '.join(re.sub(r'\b' + period + r'\b', ' ', question).split())


def brief_reply_request(message):
    question = _intent_text(message)
    question = re.sub(r"(?: (?:nhe|nha|a|ban|voi|di|duoc khong))+$", "", question)
    return bool(re.fullmatch(
        r"(?:(?:noi|tra loi|giai thich|tom tat|rut gon)(?: lai)? )?"
        r"(?:ngan|gon)(?: gon)?(?: lai)?(?: hon)?(?: (?:chut|mot chut))?", question))


def uncertain_reply(message):
    return bool(re.fullmatch(
        r"(?:(?:minh|toi) )?(?:chua biet|khong biet|chua chot|chua quyet dinh)"
        r"(?: (?:nua|gio|luc nao))?", _intent_text(message)))


def assistant_help_intent(message):
    """Recognize questions about this assistant/app by roles and question form."""
    question = _intent_text(message)
    question = re.sub(r"^(?:(?:ban|xanh non) oi |cho (?:minh|toi) (?:hoi|biet) |giup (?:minh|toi) |lam on |hay )", "", question)
    question = re.sub(r"(?: (?:nhe|nhi|voi|a|vay|di|ban|duoc khong))+$", "", question)
    subject = r"(?:ban|xanh non|chat bot|chatbot|bot|tro ly)(?: nay)?"
    app = r"(?:ung dung|app|he thong|website|trang web|dashboard|trang)(?: nay| cua ban| xanh non)?"
    if re.fullmatch(subject + r" (?:la ai|ten (?:la )?gi)", question):
        return "identity"
    if re.fullmatch(r"(?:tu )?gioi thieu(?: ve)? (?:ban than|ban|xanh non)", question):
        return "identity"
    # Restrict the open capability question to conversational role words, so
    # 'bạn giúp mình nấu món gì' doesn't become an application-help request.
    words = set(question.split())
    capability_words = set("ban xanh non chat bot chatbot tro ly nay co the lam giup ho tro tu van duoc cho minh toi nhung cac viec dieu gi nao biet khong kha nang cua thu cong chuyen ich linh vuc pham vi thong tin chuc tinh ung dung app he thong website trang web dashboard hoi nho ve noi de".split())
    own_subject = re.match(r"^(?:" + subject + "|" + app + r")\b", question)
    asking_assistant = (re.match(r"^(?:minh|toi)\b", question)
                        and re.search(r"\b(?:" + subject + r")\b", question)
                        and re.search(r"\b(hoi|nho)\b", question))
    if ((own_subject or asking_assistant) and words <= capability_words
            and re.search(r"\b(gi|nao|khong|kha nang)\b", question)
            and re.search(r"\b(lam|giup|ho tro|tu van|kha nang|chuc nang|tinh nang|hoi|nho)\b", question)):
        return "capabilities" if asking_assistant or re.match(r"^" + subject + r"\b", question) else "features"
    prefix = r"(?:(?:ban (?:hay )?|hay |giup minh |giup toi |cho minh |cho toi ))?"
    features = r"(?:gioi thieu(?: cho (?:minh|toi))?(?: ve)? |noi(?: ve)? |biet |cho (?:minh|toi) biet )?(?:cac |nhung )?(?:chuc nang|tinh nang|kha nang)(?: chinh| co ban| noi bat| quan trong| hien co| huu ich)?"
    if re.fullmatch(prefix + features + r"(?: (?:cua |tren )?(?:" + subject + "|" + app + r"))?(?: (?:la|gom|co) (?:nhung |cac )?(?:gi|nao))?", question):
        return "features"
    if re.fullmatch(prefix + r"(?:gioi thieu(?: ve)?|tim hieu(?: ve)?) " + app, question):
        return "features"
    if re.fullmatch(prefix + r"(?:huong dan(?: cach)? (?:su dung|dung)|cach (?:su dung|dung)) " + app, question):
        return "guide"
    if re.fullmatch(prefix + app + r" (?:dung|su dung) (?:the nao|ra sao)", question):
        return "guide"
    if re.fullmatch(r"(?:minh |toi )?(?:nen )?(?:bat dau tu dau|dung (?:app |ung dung )?the nao)", question):
        return "guide"
    return None


def is_activity_suggestion(message, history=()):
    """A choice of activities can imply outdoor conditions without saying AQI."""
    question = _intent_text(message)
    if _OTHER_ACTIVITY_TOPIC.search(question) and not re.search(r"\b(ra ngoai|ngoai troi)\b", question):
        return False
    activity = re.search(r"\b(hoat dong|van dong|tap)\b", question)
    choice = re.search(r"\b(gi|nao|phu hop|thich hop|goi y|de xuat|nen chon)\b", question)
    if activity and choice:
        return True
    if _PHYSICAL_ACTIVITY.search(question) and re.search(r"\b(hay|hoac|nen chon|goi y)\b", question):
        return True
    what_to_do = re.search(r"\b(?:nen |co the )?lam gi\b", question)
    if what_to_do and re.search(r"\b(hom nay|bay gio|luc nay|gio)\b", question):
        return True
    if what_to_do and history:
        previous = next((turn["content"] for turn in reversed(history) if turn.get("role") == "user"), "")
        previous = normalized(previous)
        return bool(re.search(r"\b(aqi|bui|khong khi)\b", previous) or _PHYSICAL_ACTIVITY.search(previous))
    return False


def is_activity_question(message, history=()):
    question = _intent_text(message)
    if _OTHER_ACTIVITY_TOPIC.search(question) and not re.search(r"\b(ra ngoai|ngoai troi)\b", question):
        return False
    return bool(_PHYSICAL_ACTIVITY.search(question) or is_activity_suggestion(message, history))
# A new substantive question must supply its own topic. Only recognizable
# follow-ups can inherit context, so an old AQI discussion cannot authorize an
# unrelated request such as writing Python code or giving a cooking recipe.
_FOLLOWUP = re.compile(
    r"(?:hay |ban |ban hay )?(?:giai thich|phan tich|noi|viet|trinh bay|lam ro|tom tat|so sanh)"
    r"(?: (?:them|ky|ro|cu the|chi tiet|day du|ngan gon|de hieu|don gian|ngan|lai|tiep|hon|"
    r"cau tra loi|phan truoc|noi dung tren|cho toi|cho minh|chut|mot chut|di)){0,8}"
    r"|(?:hay )?(?:tiep tuc|cho (?:minh |toi )?vi du|vi du cu the|noi ro hon|tai sao(?: vay)?|vi sao(?: vay)?)"
    r"|(?:the |vay )?(?:no|cai nay|cai do|chi so do|chi so nay|loai bui do|dieu do|dieu nay) "
    r"(?:la gi|nghia la gi|tu dau ra|anh huong the nao|anh huong gi|co hai khong|co nguy hiem khong)"
    r"|(?:the |vay )?(?:con (?:voi )?)?(?:tre em|nguoi cao tuoi|nguoi lon tuoi|nguoi nhay cam|nguoi bi hen) (?:thi sao|can chu y gi)"
    r"|(?:the |vay )?no (?:co the )?di sau (?:toi|vao) phoi (?:khong|duoc khong)"
    r"|(?:the |vay )?(?:minh|toi) (?:nen lam gi|can chu y gi|can lam gi)"
    r"|(?:the |vay )?(?:con |neu )?\d+(?: \d+)?(?: thi sao| co sao khong| co nguy hiem khong)"
    r"|hay viet tiep cau tra loi truoc tu cho dang do khong lap lai noi dung da viet"
    r"|(?:minh|toi) (?:chua hieu|khong hieu)(?: (?:lam|y ban))?"
    r"|(?:(?:minh|toi) )?(?:chua hieu|khong hieu|chua ro)(?: lam)?|y (?:ban )?la sao"
    r"|(?:(?:the|vay) )?(?:(?:minh|toi) )?(?:chua co|khong co|khong dung) may loc(?: khong khi)?(?: thi sao)?"
)


def _explicit_topic(message):
    question = _intent_text(message)
    question = re.sub(r"\bmoi truong (?:lap trinh|ao|python|lam viec)\b", " ", question)
    return bool(_ENVIRONMENT.search(question) or _OUTDOOR.search(question)
                or assistant_help_intent(message) or is_activity_question(message)
                or _VIETNAMESE_WEATHER.search(message)
                or is_known_question(message))


def is_environment_question(message, history=()):
    if _explicit_topic(message):
        return True
    if is_activity_suggestion(message, history):
        return True
    if not is_followup_question(message):
        return False
    for turn in reversed(history):
        if turn.get("role") != "user":
            continue
        if social_intent(turn["content"]):
            continue
        if _explicit_topic(turn["content"]):
            return True
        if not is_followup_question(turn["content"]):
            return False
    return False


def is_followup_question(message):
    question = _intent_text(message)
    question = re.sub(r"^(?:giup (?:minh|toi)|lam on) ", "", question)
    question = re.sub(r"(?: (?:giup minh|giup toi|duoc khong|nhe|nhi|voi|ban|a))+$", "", question)
    return bool(filter_constraint_followup(question) or _FOLLOWUP.fullmatch(question) or is_time_followup(message)
        or current_time_reply(message) or brief_reply_request(message) or uncertain_reply(message))
