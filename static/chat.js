'use strict';

(() => {
  const base = location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
  const form = document.querySelector('#chatForm');
  const input = document.querySelector('#chatInput');
  const messages = document.querySelector('#chatMessages');
  const send = document.querySelector('#chatSend');
  const reset = document.querySelector('#chatReset');
  const continueButton = document.querySelector('#chatContinue');
  const stop = document.querySelector('#chatStop');
  const status = document.querySelector('#chatStatus');
  const error = document.querySelector('#chatError');
  const suggestions = [...document.querySelectorAll('[data-chat-question]')];
  const welcome = messages.firstElementChild.cloneNode(true);
  let history = [];
  let busy = false;
  let activeController = null;
  const locationHistories = new Map();
  let historyLocation = null;

  function appendMessage(role, text) {
    const bubble = document.createElement('div');
    bubble.className = `chat-message ${role}`;
    const label = document.createElement('span');
    label.textContent = role === 'user' ? 'Bạn' : 'Xanh Non';
    const body = document.createElement('p');
    body.textContent = text;
    bubble.append(label, body);
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  }

  function setBusy(value) {
    busy = value;
    window.EnvironmentLocation?.setBusy('chat', value);
    input.disabled = value;
    send.disabled = value;
    reset.disabled = value;
    continueButton.disabled = value;
    stop.hidden = !value;
    suggestions.forEach((button) => { button.disabled = value; });
    form.setAttribute('aria-busy', String(value));
    send.textContent = value ? 'Đang trả lời…' : 'Gửi';
  }

  async function readReply(response, onEvent) {
    if (!response.headers.get('Content-Type')?.includes('text/event-stream')) {
      const result = await response.json();
      if (!response.ok) throw new Error(result.loi || 'Chưa nhận được câu trả lời.');
      return result;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result = null;
    try {
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const block = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const data = block.split('\n').filter((line) => line.startsWith('data:'))
            .map((line) => line.slice(5).trimStart()).join('\n');
          if (!data) continue; // Keepalive comments contain no reply data.
          const event = JSON.parse(data);
          if (event.type === 'error') throw new Error(event.loi);
          if (event.type === 'done') result = event;
          else onEvent(event);
        }
        if (done) break;
      }
      if (!result) throw new Error('Kết nối bị gián đoạn trước khi trả lời xong. Hãy thử lại.');
      return result;
    } finally {
      await reader.cancel().catch(() => {});
    }
  }

  async function checkReadiness() {
    try {
      const response = await fetch(`${base}/api/chat/status`);
      if (!response.ok) return;
      const result = await response.json();
      if (result.state === 'loading' || result.state === 'cold') {
        if (!busy && history.length === 0 && result.state === 'loading') {
          status.textContent = 'Xanh Non đang khởi động. Bạn có thể nhập câu hỏi trước.';
        }
        if (result.state === 'loading') setTimeout(checkReadiness, 2000);
      } else if (!busy && history.length === 0) {
        status.textContent = result.state === 'ready'
          ? 'Xanh Non đã sẵn sàng · Enter để gửi'
          : 'Chưa khởi động được Xanh Non. Gửi câu hỏi để thử lại.';
      }
    } catch (err) { /* Sending a question provides the normal connection error. */ }
  }

  function rememberReply(message, reply) {
    let context = reply.slice(-32768);
    if (/^[\uDC00-\uDFFF]/.test(context)) context = context.slice(1);
    history.push({ role: 'user', content: message }, { role: 'assistant', content: context });
    history = history.slice(-8);
  }

  async function sendMessage(message, isContinuation = false) {
    await window.EnvironmentLocation.ready;
    if (busy || !message) return;
    const locationId = window.EnvironmentLocation.current.MaDiaDiem;
    historyLocation = locationId;
    error.hidden = true;
    setBusy(true);
    continueButton.hidden = true;
    if (!isContinuation) input.value = '';
    const userBubble = appendMessage('user', isContinuation ? 'Viết tiếp' : message);
    let assistantBubble = null;
    let partialReply = '';
    status.textContent = 'Xanh Non đang suy nghĩ…';
    const slowTimer = setTimeout(() => {
      status.textContent = 'Xanh Non đang chuẩn bị câu trả lời. Lần hỏi đầu tiên có thể cần thêm thời gian.';
    }, 8000);
    const controller = new AbortController();
    activeController = controller;
    try {
      const response = await fetch(`${base}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, history: history.slice(-8), stream: true, location: locationId }),
        signal: controller.signal,
      });
      const result = await readReply(response, (event) => {
        if (event.type === 'status') status.textContent = event.text;
        if (event.type === 'delta') {
          clearTimeout(slowTimer);
          partialReply += event.text;
          if (!assistantBubble) assistantBubble = appendMessage('assistant', '');
          assistantBubble.querySelector('p').textContent = partialReply;
          messages.scrollTop = messages.scrollHeight;
          status.textContent = 'Xanh Non đang trả lời…';
        }
      });
      if (typeof result.reply !== 'string' || !result.reply.trim()) {
        throw new Error('Xanh Non chưa trả lời. Hãy thử lại.');
      }
      if (!assistantBubble) assistantBubble = appendMessage('assistant', '');
      assistantBubble.querySelector('p').textContent = result.reply;
      messages.scrollTop = messages.scrollHeight;
      rememberReply(message, result.reply);
      continueButton.hidden = !result.truncated;
      status.textContent = result.truncated
        ? 'Chọn Viết tiếp để đọc phần còn lại.'
        : 'Enter để gửi · Shift + Enter để xuống dòng';
    } catch (err) {
      const userStopped = controller.signal.reason === 'user';
      controller.abort();
      if (partialReply.trim()) {
        rememberReply(message, partialReply.trim());
        continueButton.hidden = false;
        status.textContent = userStopped
          ? 'Đã dừng. Bạn có thể chọn Viết tiếp.'
          : 'Đã giữ phần trả lời nhận được. Chọn Viết tiếp để tiếp tục.';
      } else {
        userBubble.remove();
        if (assistantBubble) assistantBubble.remove();
        if (!isContinuation) input.value = message;
        continueButton.hidden = !isContinuation;
        status.textContent = userStopped ? 'Đã dừng trả lời.' : 'Chưa nhận được câu trả lời.';
      }
      if (!userStopped) {
        error.textContent = err instanceof TypeError
          ? 'Không kết nối được chatbot. Hãy kiểm tra máy chủ đang chạy.' : err.message;
        error.hidden = false;
      }
    } finally {
      clearTimeout(slowTimer);
      activeController = null;
      locationHistories.set(locationId, history.slice());
      setBusy(false);
      input.focus();
    }
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    sendMessage(input.value.trim());
  });

  continueButton.addEventListener('click', () => {
    sendMessage('Hãy viết tiếp câu trả lời trước từ chỗ đang dở, không lặp lại nội dung đã viết.', true);
  });

  stop.addEventListener('click', () => activeController?.abort('user'));

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  suggestions.forEach((button) => button.addEventListener('click', () => {
    if (busy) return;
    input.value = button.dataset.chatQuestion;
    form.requestSubmit();
  }));

  reset.addEventListener('click', () => {
    if (busy) return;
    history = [];
    if (historyLocation) locationHistories.delete(historyLocation);
    continueButton.hidden = true;
    messages.replaceChildren(welcome.cloneNode(true));
    input.value = '';
    error.hidden = true;
    status.textContent = 'Enter để gửi · Shift + Enter để xuống dòng';
    input.focus();
  });

  checkReadiness();
  document.addEventListener('locationchange', (event) => {
    if (busy) return;
    if (historyLocation) locationHistories.set(historyLocation, history.slice());
    historyLocation = event.detail.MaDiaDiem;
    history = (locationHistories.get(historyLocation) || []).slice();
    messages.replaceChildren(welcome.cloneNode(true));
    history.forEach((item) => appendMessage(item.role, item.content));
    continueButton.hidden = true;
    error.hidden = true;
    status.textContent = `Đang trò chuyện về ${event.detail.Ten} · Enter để gửi`;
  });
})();
