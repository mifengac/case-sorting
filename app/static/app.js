/* 上传、轮询、展示结果 —— 无任何外链依赖 */
(function () {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const pickBtn = document.getElementById("pickBtn");
  const alertBox = document.getElementById("alert");
  const taskListSec = document.getElementById("taskList");
  const tasksEl = document.getElementById("tasks");
  const resultPanel = document.getElementById("resultPanel");
  const resultTitle = document.getElementById("resultTitle");
  const pagesEl = document.getElementById("pages");
  const fullTextEl = document.getElementById("fullText");
  const copyBtn = document.getElementById("copyBtn");
  const downloadBtn = document.getElementById("downloadBtn");

  /** @type {Map<string, object>} */
  const tasks = new Map();
  let activeTaskId = null;
  let pollTimer = null;

  function showAlert(msg) {
    if (!msg) {
      alertBox.hidden = true;
      alertBox.textContent = "";
      return;
    }
    alertBox.hidden = false;
    alertBox.textContent = msg;
  }

  function toast(msg) {
    let el = document.querySelector(".toast");
    if (!el) {
      el = document.createElement("div");
      el.className = "toast";
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(function () {
      el.classList.remove("show");
    }, 1800);
  }

  function statusLabel(s) {
    if (s === "pending") return "排队中";
    if (s === "processing") return "识别中";
    if (s === "done") return "已完成";
    if (s === "error") return "失败";
    return s;
  }

  function renderTasks() {
    if (tasks.size === 0) {
      taskListSec.hidden = true;
      return;
    }
    taskListSec.hidden = false;
    tasksEl.innerHTML = "";
    tasks.forEach(function (t) {
      const card = document.createElement("div");
      card.className = "task-card" + (t.task_id === activeTaskId ? " active" : "");
      card.dataset.id = t.task_id;

      const name = document.createElement("div");
      name.className = "task-name";
      name.textContent = t.original_name || t.task_id;

      const meta = document.createElement("div");
      meta.className = "task-meta";
      meta.innerHTML =
        '<span class="status ' +
        (t.status || "") +
        '">' +
        statusLabel(t.status) +
        "</span>" +
        "<span>" +
        (t.message || "") +
        "</span>" +
        (t.error
          ? '<span style="color:var(--err)">' + escapeHtml(t.error) + "</span>"
          : "");

      card.appendChild(name);
      card.appendChild(meta);

      if (t.status === "pending" || t.status === "processing") {
        const bar = document.createElement("div");
        bar.className = "progress";
        const span = document.createElement("span");
        span.style.width = Math.max(2, t.progress || 0) + "%";
        bar.appendChild(span);
        card.appendChild(bar);
      }

      card.addEventListener("click", function () {
        activeTaskId = t.task_id;
        renderTasks();
        if (t.status === "done") {
          showResult(t);
        }
      });

      tasksEl.appendChild(card);
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showResult(t) {
    resultPanel.hidden = false;
    resultTitle.textContent = "识别结果 · " + (t.original_name || "");
    pagesEl.innerHTML = "";
    const pages = t.pages || [];
    if (pages.length === 0) {
      pagesEl.innerHTML = '<p class="page-text">（无识别文本）</p>';
    } else {
      pages.forEach(function (p) {
        const block = document.createElement("div");
        block.className = "page-block";
        const title = document.createElement("div");
        title.className = "page-title";
        title.textContent = "第 " + p.page_index + " 页";
        const text = document.createElement("pre");
        text.className = "page-text";
        text.textContent = p.text || "（本页无文字）";
        block.appendChild(title);
        block.appendChild(text);
        pagesEl.appendChild(block);
      });
    }
    fullTextEl.value = t.full_text || "";
    downloadBtn.href = "/api/tasks/" + t.task_id + "/download";
    downloadBtn.setAttribute("download", "");
  }

  function anyRunning() {
    let running = false;
    tasks.forEach(function (t) {
      if (t.status === "pending" || t.status === "processing") running = true;
    });
    return running;
  }

  function ensurePolling() {
    if (pollTimer) return;
    pollTimer = setInterval(pollAll, 1200);
  }

  function stopPollingIfIdle() {
    if (!anyRunning() && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function pollAll() {
    const ids = [];
    tasks.forEach(function (t, id) {
      if (t.status === "pending" || t.status === "processing") ids.push(id);
    });
    if (ids.length === 0) {
      stopPollingIfIdle();
      return;
    }
    await Promise.all(
      ids.map(async function (id) {
        try {
          const res = await fetch("/api/tasks/" + id);
          if (!res.ok) return;
          const data = await res.json();
          tasks.set(id, data);
          if (id === activeTaskId && data.status === "done") {
            showResult(data);
          }
        } catch (e) {
          /* 轮询失败忽略，下次再试 */
        }
      })
    );
    renderTasks();
    stopPollingIfIdle();
  }

  async function uploadFiles(fileList) {
    if (!fileList || fileList.length === 0) return;
    showAlert("");
    const fd = new FormData();
    for (let i = 0; i < fileList.length; i++) {
      fd.append("files", fileList[i]);
    }
    pickBtn.disabled = true;
    try {
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) {
        showAlert(data.detail || "上传失败");
        return;
      }
      if (data.errors && data.errors.length) {
        showAlert(data.errors.join("\n"));
      }
      (data.tasks || []).forEach(function (t) {
        tasks.set(t.task_id, {
          task_id: t.task_id,
          original_name: t.original_name,
          status: t.status || "pending",
          progress: 0,
          message: "排队中",
          pages: [],
          full_text: "",
        });
        if (!activeTaskId) activeTaskId = t.task_id;
      });
      renderTasks();
      ensurePolling();
      pollAll();
    } catch (e) {
      showAlert("网络错误或服务不可用：" + e.message);
    } finally {
      pickBtn.disabled = false;
      fileInput.value = "";
    }
  }

  // 事件绑定
  pickBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    fileInput.click();
  });
  dropzone.addEventListener("click", function () {
    fileInput.click();
  });
  fileInput.addEventListener("change", function () {
    uploadFiles(fileInput.files);
  });

  ["dragenter", "dragover"].forEach(function (ev) {
    dropzone.addEventListener(ev, function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach(function (ev) {
    dropzone.addEventListener(ev, function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", function (e) {
    uploadFiles(e.dataTransfer.files);
  });

  copyBtn.addEventListener("click", async function () {
    const text = fullTextEl.value || "";
    if (!text) {
      toast("没有可复制的内容");
      return;
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        fullTextEl.hidden = false;
        fullTextEl.select();
        document.execCommand("copy");
        fullTextEl.hidden = true;
      }
      toast("已复制到剪贴板");
    } catch (e) {
      toast("复制失败，请手动选择文本");
    }
  });
})();
