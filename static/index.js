// static/index.js
let evtSource = null;
let isGenerating = false;
const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
  quotes: '""\'\'',
  highlight: function(str, lang) {
    return '<pre><code>' + md.utils.escapeHtml(str) + '</code></pre>';
  }
});

// Ensure inline code is properly rendered
md.renderer.rules.code_inline = function(tokens, idx, options, env, slf) {
  const token = tokens[idx];
  return '<code>' + md.utils.escapeHtml(token.content) + '</code>';
};

// UI Elements
const sendIcon = document.getElementById('send-icon');
const sendButton = document.querySelector('.send-button');
const sidebar = document.querySelector('.sidebar');
const overlay = document.querySelector('.overlay');

function send() {
  const prompt = document.getElementById("prompt").value.trim();
  if (!prompt || isGenerating) return;

  addBubble(prompt, "user");
  document.getElementById("prompt").value = "";
  autoResizeTextarea();

  if (evtSource) evtSource.close();

  let modelBubble = addBubble("", "model");
  let currentResponse = "";
  startGenerating();

  evtSource = new EventSource("/api/chat/stream?prompt=" + encodeURIComponent(prompt));

  evtSource.onmessage = function (event) {
    try {
      const data = JSON.parse(event.data);
      
      if (data.error) {
        modelBubble.innerHTML = md.render("Error: " + data.error);
        stopGenerating();
        return;
      }
      
      if (data.done) {
        stopGenerating();
        // Update with complete markdown-rendered response
        modelBubble.innerHTML = md.render(currentResponse);
        // Save the chat history
        fetch("/api/chat/save", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            prompt: prompt,
            response: currentResponse
          })
        });
        return;
      }
    } catch {
      // If it's not JSON, it's a token
      currentResponse += event.data;
      // Render markdown for partial response
      modelBubble.innerHTML = md.render(currentResponse);
      scrollToBottom();
    }
  };

  evtSource.onerror = function () {
    stopGenerating();
  };
}

function startGenerating() {
  isGenerating = true;
  sendIcon.textContent = 'stop';
  sendButton.onclick = stop;
  sendButton.style.background = 'var(--secondary)';
}

function stopGenerating() {
  isGenerating = false;
  sendIcon.textContent = 'send';
  sendButton.onclick = send;
  sendButton.style.background = 'var(--primary)';
  if (evtSource) evtSource.close();
}

function stop() {
  if (evtSource) {
    evtSource.close();
    stopGenerating();
  }
}

function reset() {
  // Clear the chat UI
  document.getElementById("chat").innerHTML = "";
  
  // Clear the textarea
  document.getElementById("prompt").value = "";
  autoResizeTextarea();
  
  // Stop any ongoing stream
  if (evtSource) evtSource.close();
  stopGenerating();
  
  // Reset the backend history
  fetch("/api/chat/reset", {
    method: "POST"
  });

  // Close the sidebar
  toggleSidebar();
}

function addBubble(text, type) {
  const div = document.createElement("div");
  div.className = `bubble ${type}`;
  if (type === "user") {
    div.textContent = text;
  } else {
    div.innerHTML = md.render(text);
  }
  document.getElementById("chat").appendChild(div);
  scrollToBottom();
  return div;
}

function scrollToBottom() {
  const chat = document.getElementById("chat");
  chat.scrollTop = chat.scrollHeight;
}

function toggleSidebar() {
  sidebar.classList.toggle('open');
  overlay.classList.toggle('active');
}

function toggleDarkMode() {
  const html = document.documentElement;
  const isDark = html.classList.toggle('dark');
  localStorage.setItem('darkMode', isDark);
}

// Auto-resize textarea
const textarea = document.getElementById("prompt");
textarea.addEventListener('input', autoResizeTextarea);

function autoResizeTextarea() {
  const textarea = document.getElementById("prompt");
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

// Handle Enter key to send message
textarea.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (isGenerating) {
      stop();
    } else {
      send();
    }
  }
});

// Handle mobile viewport height
function setVH() {
  const vh = window.innerHeight * 0.01;
  document.documentElement.style.setProperty('--vh', `${vh}px`);
}

// Initialize
window.onload = () => {
  // Set initial viewport height
  setVH();
  
  autoResizeTextarea();
  
  // Restore dark mode preference
  const html = document.documentElement;
  if (localStorage.getItem('darkMode') === 'true') {
    html.classList.add('dark');
  } else if (localStorage.getItem('darkMode') === 'false') {
    html.classList.remove('dark');
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    html.classList.add('dark');
    localStorage.setItem('darkMode', 'true');
  }
  
  // Load chat history
  fetch("/api/chat/history")
    .then(res => res.json())
    .then(data => {
      data.forEach(entry => {
        addBubble(entry.prompt, "user");
        addBubble(entry.response, "model");
      });
    });
};

// Update viewport height on resize and orientation change
window.addEventListener('resize', setVH);
window.addEventListener('orientationchange', setVH);
