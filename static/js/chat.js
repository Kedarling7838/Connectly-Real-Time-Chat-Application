(() => {
  const cfg = window.CHAT_CONFIG;
  const socket = io({ transports: ["websocket", "polling"] });
  const contactButtons = [...document.querySelectorAll(".contact-item")];
  const title = document.getElementById("conversationTitle");
  const subtitle = document.getElementById("conversationSubtitle");
  const messagesArea = document.getElementById("messagesArea");
  const messagesList = document.getElementById("messagesList");
  const welcomePanel = document.getElementById("welcomePanel");
  const composer = document.getElementById("composerForm");
  const input = document.getElementById("messageInput");
  const dot = document.getElementById("connectionDot");
  const connectionLabel = document.getElementById("connectionLabel");
  const toastContainer = document.getElementById("toastContainer");
  let activeId = null;
  let activeName = null;
  const seen = new Set();

  socket.on("connect", () => {
    dot.classList.add("online");
    connectionLabel.textContent = "Connected";
    socket.emit("identify");
    if (activeId) socket.emit("open_conversation", {other_id: activeId});
  });
  socket.on("disconnect", () => {
    dot.classList.remove("online");
    connectionLabel.textContent = "Reconnecting…";
  });
  socket.on("connected", () => {});
  socket.on("chat_error", data => toast(data.message || "Something went wrong."));

  contactButtons.forEach(button => button.addEventListener("click", () => {
    activeId = Number(button.dataset.userId);
    activeName = button.dataset.username;
    contactButtons.forEach(b => b.classList.toggle("active", b === button));
    title.textContent = activeName;
    subtitle.textContent = "Direct conversation";
    welcomePanel.classList.add("d-none");
    messagesArea.classList.remove("d-none");
    composer.classList.remove("d-none");
    messagesList.innerHTML = "";
    seen.clear();
    socket.emit("open_conversation", {other_id: activeId});
    input.focus();
  }));

  socket.on("conversation_history", data => {
    if (Number(data.other_id) !== activeId) return;
    messagesList.innerHTML = "";
    seen.clear();
    const messages = data.messages || [];
    if (!messages.length) addSystem("This is the beginning of your conversation. Say hello 👋");
    messages.forEach(addMessage);
    scrollToBottom();
  });

  socket.on("new_message", message => {
    const pair = [Number(message.sender_id), Number(message.recipient_id)];
    if (activeId && pair.includes(activeId) && pair.includes(Number(cfg.currentUserId))) {
      addMessage(message);
      scrollToBottom();
    }
    updateContactPreview(message);
    if (Number(message.sender_id) !== Number(cfg.currentUserId) && document.hidden) {
      toast(`New message from ${message.sender_name}`);
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(`Message from ${message.sender_name}`, {body: message.body.slice(0, 120)});
      }
    }
  });

  socket.on("contact_message", data => {
    if (Number(data.from_id) !== activeId) {
      toast(`New message from ${data.from_name}`);
    }
  });

  composer.addEventListener("submit", event => {
    event.preventDefault();
    const body = input.value.trim();
    if (!body || !activeId) return;
    socket.emit("send_message", {recipient_id: activeId, body});
    input.value = "";
    input.focus();
  });

  document.getElementById("emojiButton").addEventListener("click", () => {
    const shortcodes = [":smile:", ":heart:", ":thumbsup:", ":joy:", ":wave:", ":fire:", ":wink:"];
    const current = input.value;
    input.value = current + (current ? " " : "") + shortcodes[Math.floor(Math.random() * shortcodes.length)];
    input.focus();
  });

  function addMessage(message) {
    if (message.id && seen.has(message.id)) return;
    if (message.id) seen.add(message.id);
    const own = Number(message.sender_id) === Number(cfg.currentUserId);
    const row = document.createElement("div");
    row.className = "message-row" + (own ? " own" : "");
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = message.body || "";
    const meta = document.createElement("div");
    meta.className = "message-meta";
    const time = (message.created_at || "").slice(11, 16);
    meta.textContent = `${own ? "You" : (message.sender_name || activeName || "User")} · ${time}`;
    row.append(bubble, meta);
    messagesList.appendChild(row);
  }
  function addSystem(text) {
    const el = document.createElement("div");
    el.className = "system-message";
    el.textContent = text;
    messagesList.appendChild(el);
  }
  function updateContactPreview(message) {
    const id = Number(message.sender_id) === Number(cfg.currentUserId) ?
      Number(message.recipient_id) : Number(message.sender_id);
    const button = contactButtons.find(b => Number(b.dataset.userId) === id);
    if (button) {
      const preview = button.querySelector(".contact-preview");
      if (preview) preview.textContent = message.body;
      const time = button.querySelector(".small.text-secondary");
      if (time) time.textContent = (message.created_at || "").slice(11, 16);
      button.parentElement.prepend(button);
    }
  }
  function scrollToBottom() {
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }
  function toast(text) {
    const el = document.createElement("div");
    el.className = "toast show text-bg-dark border-0 mb-2";
    el.setAttribute("role", "status");
    el.innerHTML = `<div class="d-flex"><div class="toast-body"></div><button type="button" class="btn-close btn-close-white me-2 m-auto" aria-label="Close"></button></div>`;
    el.querySelector(".toast-body").textContent = text;
    el.querySelector("button").addEventListener("click", () => el.remove());
    toastContainer.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }
  if ("Notification" in window && Notification.permission === "default") {
    // Request only after the user interacts with the page.
    document.addEventListener("click", function requestNotification() {
      Notification.requestPermission().catch(() => {});
      document.removeEventListener("click", requestNotification);
    }, {once: true});
  }
})();
