// static/index.js
let evtSource = null;

function send() {
  const prompt = document.getElementById("prompt").value.trim();
  if (!prompt) return;

  addBubble(prompt, "user");
  document.getElementById("prompt").value = "";
  autoResizeTextarea();

  if (evtSource) evtSource.close();

  let modelBubble = addBubble("", "model");

  evtSource = new EventSource("/api/chat/stream?prompt=" + encodeURIComponent(prompt));

  evtSource.onmessage = function (event) {
    if (event.data === "[DONE]") {
      evtSource.close();
      return;
    }
    modelBubble.textContent += event.data;
    scrollToBottom();
  };

  evtSource.onerror = function () {
    evtSource.close();
  };
}

function stop() {
  if (evtSource) evtSource.close();
}

function addBubble(text, type) {
  const div = document.createElement("div");
  div.className = `bubble ${type}`;
  div.textContent = text;
  document.getElementById("chat").appendChild(div);
  scrollToBottom();
  return div;
}

function scrollToBottom() {
  const chat = document.getElementById("chat");
  chat.scrollTop = chat.scrollHeight;
}

// Auto-resize textarea for better UX on mobile
const textarea = document.getElementById("prompt");
textarea.addEventListener('input', autoResizeTextarea);
function autoResizeTextarea() {
  textarea.style.height = 'auto';
  textarea.style.height = (textarea.scrollHeight) + 'px';
}

window.onload = () => {
  autoResizeTextarea();
  fetch("/api/chat/history")
    .then(res => res.json())
    .then(data => {
      data.forEach(entry => {
        addBubble(entry.prompt, "user");
        addBubble(entry.response, "model");
      });
    });
};
