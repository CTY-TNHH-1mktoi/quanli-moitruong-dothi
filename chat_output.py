"""Filter generated prose before it reaches JSON clients or live chat bubbles."""

import re
import unicodedata


_BOUNDARY = re.compile(r"\r?\n+|[.!?。][\"')\]»*_]*(?:[ \t]+)")
_INTERNAL = re.compile(
    r"khong tu them loi khuyen|khong suy doan tuoi|khong chep lai toan bo bang"
    r"|khong them y ngoai cau hoi|khong dung (?:ky hieu )?markdown"
    r"|dung so lieu bang giam sat trong cau hoi moi nhat"
    r"|phan biet cau hoi gia dinh voi so do thuc te"
    r"|(?:chi )?tra loi thang trong|tra loi chi tiet vua du trong"
    r"|tra loi bang tieng viet|van ban thuan khong co ky hieu"
    r"|ket luan truoc, ly do sau|nguoi dung yeu cau giai thich chi tiet"
    r"|noi dung tra loi danh cho nguoi dung|cac chi dan ve cach tra loi"
    r"|su dung so do trong du lieu moi nhat|cau hoi gia dinh duoc giai thich theo"
    r"|thong tin suc khoe chi giai thich|giai thich trong khoang 4"
    r"|di thang vao cau tra loi trong 2|giao tiep tu nhien bang tieng viet"
    r"|tra loi dung noi dung duoc hoi bang cac du lieu lien quan"
    r"|chi bao thieu du lieu khi chi so do can de tra loi cau hoi"
    r"|chi giai thich cac tac dong duoc neu o day"
    r"|(?:chi dan|huong dan|quy tac|yeu cau) noi bo"
    r"|(?:system|assistant|user)\s*(?:prompt|instruction|role)"
    r"|<\|(?:im_start|im_end|system|assistant|user)\|>"
)
_INCOMPLETE_INTERNAL = (
    "khong tu them loi khuyen", "khong suy doan tuoi", "khong chep lai toan bo bang",
    "khong dung markdown", "chi tra loi thang trong", "tra loi bang tieng viet",
    "chi dan noi bo", "huong dan noi bo", "system prompt",
    "noi dung tra loi danh cho nguoi dung", "cac chi dan ve cach tra loi",
    "su dung so do trong du lieu moi nhat", "cau hoi gia dinh duoc giai thich theo",
    "thong tin suc khoe chi giai thich", "di thang vao cau tra loi trong 2",
)
_SPEECH = re.compile(r"^(?:kinh thua|kinh chuc|xin kinh chuc|tran trong cam on)\b")
_FALLBACK = "Mình chưa tạo được câu trả lời phù hợp. Bạn hãy đặt lại câu hỏi cụ thể hơn."
_RETIRED_INTRO = re.compile(
    r"chao[,\s]*toi la chat\s*bot moi truong xanh non[,\s]*"
    r"toi co the giup gi cho ban[.!?\s]*"
)
_QUESTION_META = re.compile(
    r"^(?:tuy nhien[, :]*)?(?:khong|chua) co (?:thong tin|du lieu|so lieu)\b"
    r"[^!?\n]*\btrong (?:cau hoi|yeu cau)(?: cua ban)?\b"
    r"|^(?:cau hoi|yeu cau)(?: cua ban)? (?:khong|chua) (?:cung cap|de cap|neu)\b"
)


def _fold(text):
    return "".join(char for char in unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
                   if not unicodedata.combining(char))


def has_dangling_intro(text):
    """A promise to list measures is not an answer, even after a model EOS."""
    folded = _fold(_without_markup(text)).strip()
    folded = re.sub(r"(?:\n\s*(?:[-*•]|\d+[.)])\s*)+$", "", folded).strip()
    return bool(re.search(
        r"\b(?:(?:cac|mot so|nhung) (?:bien phap|giai phap|goi y|buoc|cach)(?: cu the)? "
        r"(?:sau|sau day|duoi day)|nhu sau|bao gom|following (?:steps|measures|tips)|as follows)\s*[:.]?$",
        folded))


def _without_markup(text):
    text = text.replace("\\*", "*").replace("**", "")
    return re.sub(r"(?m)^[ \t]*#{1,6}[ \t]+", "", text)


def _is_internal(text):
    folded = _fold(_without_markup(text)).strip()
    candidate = re.sub(r"^(?:luu y|ghi chu)\s*:\s*", "", folded).strip(" *_`\\:")
    return bool(_INTERNAL.search(folded) or
                (len(candidate) >= 6 and any(signature.startswith(candidate) for signature in _INCOMPLETE_INTERNAL)))


def _clean_piece(text):
    text = _without_markup(text)
    folded = _fold(text).strip()
    if folded.startswith("kinh thua") and "," in text:
        text = text[text.index(",") + 1:].lstrip()
        folded = _fold(text).strip()
    if folded.rstrip(" :*_`\\") in {"luu y", "ghi chu"}:
        return ""
    if (_SPEECH.search(folded) or _is_internal(text) or _QUESTION_META.search(folded)
            or _RETIRED_INTRO.fullmatch(folded)):
        return ""
    # Empty bullet/heading fragments must not become a visible answer.
    return text if text.strip(" \t\r\n\\*_`#:-") else ""


class ReplyFilter:
    """Hold each unfinished sentence so instruction fragments cannot leak in deltas."""

    def __init__(self, on_text=None):
        self.on_text = on_text
        self.pending = ""
        self.parts = []
        self.separator = ""
        self.received = False
        self.suppress_sentence = False

    def _publish(self, text):
        text = _clean_piece(text)
        if not text.strip():
            return
        if not self.parts:
            text = text.lstrip()
        text = self.separator + text
        content = text.rstrip()
        self.separator = text[len(content):]
        if content:
            self.parts.append(content)
            if self.on_text is not None:
                self.on_text(content)

    def feed(self, text):
        if not text:
            return
        self.received = True
        self.pending += text
        self.pending = self.pending.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\\n", "\n")
        while True:
            boundary = _BOUNDARY.search(self.pending)
            if boundary is None:
                break
            piece = self.pending[:boundary.end()]
            internal = _is_internal(piece)
            if not self.suppress_sentence and not internal:
                self._publish(piece)
            if self.suppress_sentence or internal:
                self.suppress_sentence = not bool(re.search(r"[.!?。][\"')\]»*_]*\s*$", piece))
            self.pending = self.pending[boundary.end():]

    def finish(self, fallback=True):
        if not self.suppress_sentence:
            self._publish(self.pending)
        self.pending = ""
        if not self.parts and fallback:
            self._publish(_FALLBACK)
        return "".join(self.parts)


def clean_reply(text, fallback=True):
    output = ReplyFilter()
    output.feed(text)
    return output.finish(fallback=fallback)
