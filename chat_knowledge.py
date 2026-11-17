"""Retrieve only the project's source-checked knowledge, never raw chat datasets."""

from functools import lru_cache
import json
import logging
from pathlib import Path
import re
import unicodedata


KNOWLEDGE_PATH = Path(__file__).resolve().parent / "data" / "xanhnon" / "knowledge.json"
logger = logging.getLogger(__name__)
NO_FILTER_PHRASE = r"(?:chua|khong) (?:co|dung|mua(?: duoc)?|sam(?: duoc)?) may loc(?: khong khi)?"


def normalized(text):
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"pm\s*2[.,]\s*5", "pm25", text)
    text = re.sub(r"pm\s*10", "pm10", text)
    return " ".join(re.findall(r"\w+", text))


def filter_constraint_followup(message):
    return bool(re.fullmatch(
        r"(?:(?:the|vay) )?(?:neu )?(?:(?:minh|toi) )?" + NO_FILTER_PHRASE
        + r"(?: (?:thi (?:sao|lam sao|lam gi)|(?:con|co) cach nao(?: khac| lam ngay)?(?: khong)?))?",
        normalized(message)))


@lru_cache(maxsize=1)
def _load_index(modified_ns):
    from sklearn.feature_extraction.text import TfidfVectorizer
    knowledge = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    documents = knowledge["documents"]
    aliases, owners, exact = [], [], {}
    for index, document in enumerate(documents):
        for question in document["questions"] + [document["title"]]:
            question = normalized(question)
            exact[question] = index
            aliases.append(question)
            owners.append(index)
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    matrix = vectorizer.fit_transform(aliases)
    return documents, knowledge["sources"], vectorizer, matrix, owners, exact


def _index():
    try:
        return _load_index(KNOWLEDGE_PATH.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError):
        logger.exception("Không đọc được kho kiến thức Xanh Non")
        return None


@lru_cache(maxsize=2)
def _documents(path, modified_ns):
    return json.loads(Path(path).read_text(encoding="utf-8"))["documents"]


def _verified_documents():
    try:
        return _documents(str(KNOWLEDGE_PATH), KNOWLEDGE_PATH.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError):
        logger.exception("Không đọc được kiến thức đã kiểm tra")
        return []


@lru_cache(maxsize=2)
def _exact_catalog(path, modified_ns):
    """Exact aliases need a small JSON lookup, not a fitted search index."""
    documents = _documents(path, modified_ns)
    return {normalized(question): doc for doc in documents for question in doc["questions"] + [doc["title"]]}


def _exact_document(message):
    try:
        return _exact_catalog(str(KNOWLEDGE_PATH), KNOWLEDGE_PATH.stat().st_mtime_ns).get(normalized(message))
    except (OSError, ValueError, KeyError, TypeError):
        logger.exception("Không đọc được danh mục kiến thức Xanh Non")
        return None


def _topic_ids(query):
    advice = advice_topic(query)
    if advice:
        return [advice]
    particles = re.search(r"\b(bui|pm25|pm10)\b", query)
    if particles and re.search(r"\b(trong nha|trong phong|vao nha)\b", query):
        if not re.search(r"\b(chua co|thieu|bi trong|khong co so|khong co du lieu)\b", query):
            return ["indoor_particles"]
    if particles and re.search(r"\b(tu dau|o dau|nguon|phat sinh|sinh ra)\b", query):
        return ["pm_sources"]
    if "pm25" in query and "pm10" in query:
        return ["pm_comparison"]
    if particles and "aqi" in query and re.search(r"\b(khac|nham|thay|cung|don vi)\b", query):
        return ["pm_aqi_difference", "pm_units"]
    if "pm25" in query and re.search(r"\b(nho|kich thuoc|phoi|la gi|loai bui)\b", query):
        return ["pm25_definition"]
    if "aqi" in query and re.search(r"\b\d{1,3}\b|\b(cac muc|phan loai|thang)\b", query):
        return ["aqi_categories", "outdoor_principles"]
    return []


def advice_topic(message, history=()):
    """Choose reviewed practical guidance only for a clear request for measures."""
    query = normalized(message)
    if re.search(r"\b(bao nhieu|so lieu|so do|du lieu|du bao|aqi|tai sao|vi sao|la gi|so sanh|"
                 r"ke thuoc|uong thuoc|kho tho|dau nguc|bat tinh|chan doan|"
                 r"viet cau mo dau|viet loi dan|tieu de)\b", query):
        return None
    constraint = filter_constraint_followup(query)
    continuation = (query == "hay viet tiep cau tra loi truoc tu cho dang do khong lap lai noi dung da viet")
    action_followup = bool(re.fullmatch(
        r"(?:(?:the|vay) )?(?:(?:minh|toi) )?(?:(?:nen|can|co the) )?lam gi"
        r"(?: (?:bay gio|tiep|tiep theo))?(?: (?:nhe|nhi|ban|a))?", query))
    if (constraint or continuation or action_followup) and history:
        from chat_scope import social_intent
        for index in range(len(history) - 1, -1, -1):
            turn = history[index]
            if turn.get("role") == "user" and not social_intent(turn["content"]):
                if action_followup:
                    return advice_topic(turn["content"] + " " + message, history[:index])
                if constraint:
                    return advice_topic("cach xu ly " + turn["content"], history[:index])
                return advice_topic(turn["content"], history[:index])
    action = re.search(r"\b(lam sao|lam the nao|lam gi|xu ly|bien phap|giai phap|cach|"
                       r"giam|han che|ngan|phong ngua|phong tranh|phong nam moc|chon|su dung|nen dung|phan loai|bat dau|bao ve tai|quen tai|o lau|nghe lau|tang thoi gian|tiep xuc)\b", query)
    if not action:
        return None
    topics = []
    particles = re.search(r"\b(bui|pm25|pm10)\b", query)
    home = re.search(r"\b(trong nha|vao nha|trong phong|phong|nha|tuong)\b", query)
    cleaner = re.search(r"\b(may loc khong khi|hepa|cadr)\b", query)
    cleaner_use = re.search(r"\b(chon|cadr|su dung|van hanh|nen dung|dung hepa|dung may loc)\b", query)
    if cleaner and cleaner_use and not re.search(NO_FILTER_PHRASE, query):
        topics.append("filter_actions")
    elif particles and home:
        topics.append("indoor_dust_actions")
    if home and re.search(r"\b(do am|am thap|nom am|am qua|nam moc|am moc|phong moc|bi uot)\b", query):
        topics.append("humidity_actions")
    if re.search(r"\b(tieng on|do on|on qua|loa lon|loa to|noi on|cho on|nguon on|am thanh lon|tieng lon|bao ve tai|nut tai|chup tai)\b", query):
        topics.append("noise_actions")
    if re.search(r"\b(rac|chat thai|rac nhua|nhua mot lan|nhua dung mot lan|do nhua mot lan|song xanh)\b", query):
        topics.append("waste_actions")
    if re.search(r"\b(troi nong|troi nang|nang nong|nang gat|thoi tiet nong)\b", query):
        topics.append("heat_actions")
    return topics[0] if len(topics) == 1 else None


def practical_answer(message, history=(), detailed=False, documents=None):
    document_id = advice_topic(message, history)
    if not document_id:
        return None
    if documents is None:
        documents = _verified_documents()
    document = next((doc for doc in documents if doc["id"] == document_id), None)
    if document is None:
        return None
    if document_id == "indoor_dust_actions" and re.search(NO_FILTER_PHRASE, normalized(message)):
        return document["answer_without_filter"]
    if detailed:
        return "\n".join(f"{index + 1}. {step}" for index, step in enumerate(document["steps"]))
    return document["answer"]


def retrieve(message, limit=3):
    index = _index()
    if index is None:
        return []
    documents, sources, vectorizer, matrix, owners, exact = index
    query = normalized(message)
    if not query:
        return []
    scores = (matrix @ vectorizer.transform([query]).T).toarray().ravel()
    best = {}
    for owner, score in zip(owners, scores):
        best[owner] = max(best.get(owner, 0), float(score))
    if query in exact:
        best[exact[query]] = 1.0
    # Conversational negatives must not select missing-data FAQs by accident.
    topics = _topic_ids(query)
    if topics and query not in exact:
        best = {i: 0.95 - topics.index(doc["id"]) * 0.01
                for i, doc in enumerate(documents) if doc["id"] in topics}
    results = []
    for owner, score in sorted(best.items(), key=lambda pair: pair[1], reverse=True):
        if score < 0.34 or len(results) >= limit:
            break
        doc = documents[owner]
        results.append({**doc, "score": round(score, 4), "exact": exact.get(query) == owner,
                        "sources": [sources[source_id] for source_id in doc["source_ids"]]})
    return results


def exact_answer(message):
    """Only explicit known FAQs bypass generation; current readings don't."""
    document = _exact_document(message)
    return document["answer"] if document else None


def concept_answer(message, history=(), documents=None, detailed=False):
    """Use reviewed facts for clear comparisons and particle follow-ups."""
    query = normalized(message)
    from chat_scope import is_followup_question, social_intent
    if (is_followup_question(message) and re.search(r"\b(giai thich|noi ro|noi de hieu|lam ro)\b", query)
            and not re.search(r"\b(aqi|pm25|pm10|bui|thoi tiet|nhiet do|do am|tieng on)\b", query)):
        for index in range(len(history) - 1, -1, -1):
            turn = history[index]
            if turn.get("role") == "user" and not social_intent(turn["content"]):
                if re.search(r"\b(hien tai|hom nay|bay gio|luc nay)\b", normalized(turn["content"])):
                    return None
                return concept_answer(turn["content"], history[:index], documents, detailed)
    document_id = None
    first_sentence = False
    first_two = False
    particles = re.search(r"\b(pm25|pm10|bui)\b", query)
    current = re.search(r"\b(hien tai|hom nay|bay gio|luc nay|dang do|so do moi)\b", query)
    if particles and "aqi" in query and re.search(r"\b(giong|dong nghia|bang|thay|quy doi|lam aqi|lam us aqi)\b", query):
        document_id, first_sentence = "pm_aqi_difference", True
    elif "pm25" in query and "pm10" in query and re.search(r"\b(khac|phan biet|so sanh)\b", query) and not current:
        document_id, first_sentence = "pm_comparison", True
    elif not current and particles and re.search(r"\b(tu dau|nguon goc|sinh ra|phat sinh)\b", query):
        document_id = "pm_sources"
    elif not current and particles and re.search(r"\b(trong nha|trong phong|o nha)\b", query) and re.search(r"\b(het lo|tranh het|co chac|co the|van co|khong co bui)\b", query):
        document_id = "indoor_particles"
    elif not current and "pm25" in query and "pm10" not in query and re.search(r"\b(nho toi muc|nho co nao|kich thuoc|duong kinh|vao phoi)\b", query):
        document_id, first_two = "pm25_definition", True
    elif not current and "aqi" in query and not particles and not re.search(r"\d|\b(vi sao|tai sao|cach tinh|du bao|ngay mai)\b", query) and re.search(r"\b(giai thich|y nghia|dung de|bieu thi|noi len|la gi|nghia la)\b", query):
        document_id = "aqi_definition"
    elif history and is_particle_followup(message, history):
        document_id, first_sentence = "pm_health", True
    else:
        from chat_scope import is_followup_question, social_intent
        previous = next((turn['content'] for turn in reversed(history)
                         if turn.get('role') == 'user' and not social_intent(turn['content'])), '')
        topic = query
        if (is_followup_question(message) and re.search(r"\b(giai thich|noi|lam ro)\b", query)
                and not re.search(r"\b(aqi|pm25|pm10|bui)\b", query)):
            topic = normalized(previous)
        if not re.search(r"\b\d+(?: \d+)?\b", topic):
            if re.search(r"\b(la gi|nghia la gi)\b", topic) and not re.search(r"\b(va|hoac)\b", topic):
                subjects = [term for term in ('pm25', 'pm10', 'aqi') if re.search(r'\b' + term + r'\b', topic)]
                if len(subjects) == 1:
                    document_id = {'pm25': 'pm25_definition', 'pm10': 'pm10_definition', 'aqi': 'aqi_definition'}[subjects[0]]
            elif (re.search(r"\b(co hai|vo hai|nguy hiem|anh huong|tac hai)\b", query)
                  and re.search(r"\b(pm25|pm10|bui)\b", query + ' ' + normalized(previous))):
                document_id, first_sentence = 'pm_health', True
    if not document_id:
        return None
    if documents is None:
        documents = _verified_documents()
    answer = next((doc["answer"] for doc in documents if doc["id"] == document_id), None)
    if answer and detailed and document_id == "aqi_definition":
        levels = next((doc["answer"] for doc in documents if doc["id"] == "aqi_categories"), "")
        return answer + ("\n\n" + levels if levels else "")
    if detailed:
        return answer
    if answer and first_two:
        return answer.split("; ", 1)[0].rstrip(".") + "."
    if answer and first_sentence:
        answer = answer.split(". ", 1)[0].rstrip(".") + "."
    return answer


def is_particle_followup(message, history):
    from chat_scope import is_followup_question, social_intent
    if not is_followup_question(message) or not re.search(r"\bphoi\b", normalized(message)):
        return False
    previous = next((turn["content"] for turn in reversed(history)
                     if turn["role"] == "user" and not social_intent(turn["content"])), "")
    return bool(re.search(r"\b(pm25|pm10|bui)\b", normalized(previous)))


def is_known_question(message):
    """Recognize a source-backed FAQ without treating a fuzzy match as a topic."""
    return _exact_document(message) is not None


def reference_context(message, history=()):
    query = message
    from chat_scope import is_followup_question, social_intent
    if is_followup_question(message):
        previous = next((turn["content"] for turn in reversed(history)
                         if turn["role"] == "user" and not social_intent(turn["content"])), "")
        if previous:
            query = previous + " " + message
    matches = retrieve(query)
    if not matches:
        return ""
    parts = ["Kiến thức tham chiếu đã kiểm tra nguồn; đây không phải số đo hiện tại:"]
    for match in matches:
        parts.append(f"{match['title']}: {match['answer']}")
        for source in match["sources"]:
            if source["type"] == "official":
                parts.append(f"Nguồn: {source['title']} — {source['url']}")
    return "\n".join(parts) + "\n\n"
