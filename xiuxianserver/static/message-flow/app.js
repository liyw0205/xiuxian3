(function () {
  const config = window.MESSAGE_FLOW_CONFIG || {};
  const state = {
    filter: "all",
    records: new Map(),
    counts: {
      incoming: 0,
      outgoing: 0,
    },
  };

  const nodes = {
    statusBadge: document.getElementById("statusBadge"),
    playerBadge: document.getElementById("playerBadge"),
    retentionBadge: document.getElementById("retentionBadge"),
    loginPanel: document.getElementById("loginPanel"),
    loginLink: document.getElementById("loginLink"),
    flowPanel: document.getElementById("flowPanel"),
    flowList: document.getElementById("flowList"),
    emptyState: document.getElementById("emptyState"),
    totalCount: document.getElementById("totalCount"),
    incomingCount: document.getElementById("incomingCount"),
    outgoingCount: document.getElementById("outgoingCount"),
    latestTime: document.getElementById("latestTime"),
    autoScroll: document.getElementById("autoScroll"),
    filterButtons: Array.from(document.querySelectorAll("[data-filter]")),
  };

  function init() {
    nodes.retentionBadge.textContent = `保留 ${config.retentionText || "短期"}`;
    if (!config.loggedIn) {
      showLogin();
      return;
    }

    nodes.playerBadge.textContent = `主用户 ${config.playerId || "--"}`;
    nodes.flowPanel.hidden = false;
    bindFilters();
    loadRecent().then(connectStream);
  }

  function showLogin() {
    setStatus("待登录", "is-warn");
    nodes.loginPanel.hidden = false;
    nodes.playerBadge.textContent = "未登录";
    nodes.loginLink.href = config.loginUrl || "/xiuxian/user-groups";
  }

  function bindFilters() {
    nodes.filterButtons.forEach((button) => {
      button.addEventListener("click", () => {
        state.filter = button.dataset.filter || "all";
        nodes.filterButtons.forEach((item) => item.classList.toggle("is-active", item === button));
        applyFilter();
      });
    });
  }

  async function loadRecent() {
    setStatus("读取中", "is-idle");
    try {
      const response = await fetch(config.recentUrl || "/xiuxian/message-flow/api/recent?limit=160");
      if (response.status === 401) {
        nodes.flowPanel.hidden = true;
        showLogin();
        return;
      }
      if (!response.ok) {
        setStatus("读取失败", "is-bad");
        return;
      }
      const data = await response.json();
      (data.records || []).forEach(appendRecord);
      setStatus("等待实时", "is-warn");
    } catch (_error) {
      setStatus("读取失败", "is-bad");
    }
  }

  function connectStream() {
    const streamUrl = config.streamUrl || "/xiuxian/message-flow/stream";
    const source = new EventSource(streamUrl);

    source.onopen = () => setStatus("实时连接", "is-live");
    source.onerror = () => setStatus("重连中", "is-warn");
    source.onmessage = (event) => {
      try {
        appendRecord(JSON.parse(event.data));
      } catch (_error) {
        setStatus("消息解析失败", "is-bad");
      }
    };
  }

  function appendRecord(record) {
    const flowId = String(record && record.flow_id ? record.flow_id : "");
    if (!flowId || state.records.has(flowId)) {
      return;
    }

    const direction = record.direction === "outgoing" ? "outgoing" : "incoming";
    const row = document.createElement("article");
    row.className = `flow-row ${direction}`;
    row.dataset.direction = direction;
    row.dataset.flowId = flowId;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.appendChild(renderMeta(record, direction));
    bubble.appendChild(renderContent(record));

    row.appendChild(bubble);
    nodes.flowList.appendChild(row);
    state.records.set(flowId, { record, row });
    state.counts[direction] += 1;

    updateStats(record);
    applyFilterToRow(row);
    nodes.emptyState.classList.toggle("is-hidden", state.records.size > 0);
    if (nodes.autoScroll.checked) {
      nodes.flowList.scrollTop = nodes.flowList.scrollHeight;
    }
  }

  function renderMeta(record, direction) {
    const meta = document.createElement("div");
    meta.className = "flow-meta";
    meta.appendChild(tag(record.adapter || "unknown"));
    meta.appendChild(tag(direction === "outgoing" ? "发出" : "收到", "direction"));
    if (record.message_type) {
      meta.appendChild(tag(record.message_type));
    }
    const time = document.createElement("span");
    time.textContent = compactTime(record.created_at);
    meta.appendChild(time);
    return meta;
  }

  function renderContent(record) {
    const content = document.createElement("div");
    content.className = "content";
    content.innerHTML = record.content_html || escapeHtml(record.content || "");
    hardenLinks(content);
    return content;
  }

  function tag(text, extraClass) {
    const item = document.createElement("span");
    item.className = extraClass ? `tag ${extraClass}` : "tag";
    item.textContent = text;
    return item;
  }

  function updateStats(record) {
    nodes.totalCount.textContent = String(state.records.size);
    nodes.incomingCount.textContent = String(state.counts.incoming);
    nodes.outgoingCount.textContent = String(state.counts.outgoing);
    nodes.latestTime.textContent = compactTime(record.created_at) || "--";
  }

  function applyFilter() {
    state.records.forEach(({ row }) => applyFilterToRow(row));
  }

  function applyFilterToRow(row) {
    const hidden = state.filter !== "all" && row.dataset.direction !== state.filter;
    row.classList.toggle("is-hidden", hidden);
  }

  function setStatus(text, className) {
    nodes.statusBadge.textContent = text;
    nodes.statusBadge.className = `status-badge ${className || "is-idle"}`;
  }

  function compactTime(value) {
    if (!value) {
      return "";
    }
    const text = String(value).replace("T", " ");
    return text.length > 16 ? text.slice(5, 16) : text;
  }

  function escapeHtml(text) {
    return String(text || "").replace(/[&<>"]/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
    }[char]));
  }

  function hardenLinks(root) {
    root.querySelectorAll("a[href]").forEach((link) => {
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    });
  }

  init();
}());
