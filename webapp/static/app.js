/* 智慧课堂分析系统 - 前端逻辑 */
"use strict";

const $ = (id) => document.getElementById(id);

const els = {
  fileInput: $("fileInput"),
  dropzone: $("dropzone"),
  fileChip: $("fileChip"),
  analyzeBtn: $("analyzeBtn"),
  uploadTip: $("uploadTip"),
  progressCard: $("progressCard"),
  pStatus: $("pStatus"),
  pMessage: $("pMessage"),
  pFill: $("pFill"),
  pNum: $("pNum"),
  resultCard: $("resultCard"),
  rTitle: $("rTitle"),
  rSub: $("rSub"),
  rActions: $("rActions"),
  metricsGrid: $("metricsGrid"),
  mediaWrap: $("mediaWrap"),
  mediaViewer: $("mediaViewer"),
  dashImg: $("dashImg"),
  reportText: $("reportText"),
  historyList: $("historyList"),
  errorToast: $("errorToast"),
  healthDot: $("healthDot"),
  healthText: $("healthText"),
};

const IMG_EXT = new Set([".jpg", ".jpeg", ".png", ".bmp"]);
const VDO_EXT = new Set([".mp4", ".avi", ".mov", ".mkv"]);

let selectedFile = null;
let viewJobId = null;
let pollTimer = null;
let activeResultJobId = null; // 当前结果区展示的任务（避免请求过期覆盖）

/* ---------------- 通用 ---------------- */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { hour12: false });
}

function statusText(st) {
  return { pending: "排队中", running: "分析中", done: "已完成", error: "失败" }[st] || st;
}

function toast(msg) {
  els.errorToast.textContent = msg;
  els.errorToast.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (els.errorToast.hidden = true), 6000);
}

async function api(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

/* ---------------- 健康检查 ---------------- */
async function checkHealth() {
  try {
    await api("/api/health");
    els.healthDot.className = "dot ok";
    els.healthText.textContent = "服务已连接";
  } catch (_) {
    els.healthDot.className = "dot err";
    els.healthText.textContent = "服务未连接";
  }
}

/* ---------------- 文件选择 ---------------- */
function extOf(name) {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

function setFile(file) {
  if (!file) return;
  const ext = extOf(file.name);
  if (!IMG_EXT.has(ext) && !VDO_EXT.has(ext)) {
    toast("不支持的文件格式，请选择图片或视频");
    return;
  }
  selectedFile = file;
  const kind = VDO_EXT.has(ext) ? "视频" : "图片";
  els.fileChip.hidden = false;
  els.fileChip.textContent = `${kind} · ${file.name}（${(file.size / 1024 / 1024).toFixed(1)} MB）`;
  els.analyzeBtn.disabled = false;
  els.uploadTip.textContent = "";
}

function bindUpload() {
  els.dropzone.addEventListener("click", () => els.fileInput.click());
  els.dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); els.fileInput.click(); }
  });
  els.fileInput.addEventListener("change", () => setFile(els.fileInput.files[0]));

  ["dragover", "dragenter"].forEach((ev) =>
    els.dropzone.addEventListener(ev, (e) => { e.preventDefault(); els.dropzone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    els.dropzone.addEventListener(ev, (e) => { e.preventDefault(); els.dropzone.classList.remove("drag"); }));
  els.dropzone.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0]));

  els.analyzeBtn.addEventListener("click", uploadFile);
  $("refreshBtn").addEventListener("click", refreshHistory);
}

/* ---------------- 上传 & 轮询 ---------------- */
async function uploadFile() {
  if (!selectedFile) return;
  const form = new FormData();
  form.append("file", selectedFile);

  els.analyzeBtn.disabled = true;
  els.analyzeBtn.textContent = "上传中…";
  els.uploadTip.textContent = "";
  try {
    const data = await api("/api/analyze", { method: "POST", body: form });
    const job = data.job;
    els.fileChip.hidden = true;
    selectedFile = null;
    els.analyzeBtn.textContent = "开始分析";
    startPoll(job.id);
    refreshHistory();
  } catch (e) {
    toast("上传失败：" + e.message);
    els.analyzeBtn.disabled = false;
    els.analyzeBtn.textContent = "开始分析";
  }
}

function startPoll(jobId) {
  viewJobId = jobId;
  els.progressCard.hidden = false;
  if (pollTimer) clearInterval(pollTimer);
  const tick = async () => {
    if (!viewJobId) return;
    try {
      const { job } = await api(`/api/jobs/${viewJobId}`);
      renderProgress(job);
      if (job.status === "done") { renderResult(job); stopPoll(); refreshHistory(); }
      else if (job.status === "error") { renderError(job); stopPoll(); refreshHistory(); }
    } catch (e) {
      if (viewJobId) toast("查询进度失败：" + e.message);
      stopPoll();
    }
  };
  tick();
  pollTimer = setInterval(tick, 900);
}

function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  viewJobId = null;
}

/* ---------------- 渲染 ---------------- */
function renderProgress(job) {
  els.pStatus.className = "badge " + job.status;
  els.pStatus.textContent = statusText(job.status);
  els.pMessage.textContent = job.message || "";
  const p = Math.max(0, Math.min(100, Math.round(job.progress || 0)));
  els.pFill.style.width = p + "%";
  els.pNum.textContent = p + "%";
  if (job.status === "error") els.pNum.textContent = "处理失败";
}

function metric(k, v, extra) {
  return `<div class="metric ${extra || ""}"><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`;
}

function renderResult(job) {
  if (job.status !== "done") return;
  activeResultJobId = job.id;
  els.resultCard.hidden = false;
  els.rTitle.textContent = `分析结果 · ${job.filename}`;
  els.rSub.textContent = `生成于 ${fmtTime(job.finished_at)}`;

  const s = job.summary || {};
  const avg = Number(s.avg_attention || 0).toFixed(1);
  const isVdo = !!s.is_video;
  const pctBar = `<div class="bar"><i style="width:${Math.max(0, Math.min(100, Number(s.avg_attention || 0)))}%"></i></div>`;

  let grid = "";
  grid += metric("估算学生人数", `${s.unique_students ?? 0}<small> 人</small>`);
  grid += metric("检测人次", `${s.total_samples ?? 0}<small> 人次</small>`);
  grid += metric("平均专注度", `${avg}<small> %</small>`, "attention") + pctBar;
  grid += metric("专注度范围", `${Number(s.min_attention ?? 0).toFixed(0)} – ${Number(s.max_attention ?? 0).toFixed(0)}<small> %</small>`);
  grid += metric("中位专注度", `${Number(s.median_attention ?? 0).toFixed(1)}<small> %</small>`);
  if (isVdo) grid += metric("课堂时长", `${Math.round(s.video_duration || 0)}<small> 秒</small>`);
  else grid += metric("分析类型", "课堂图片");
  els.metricsGrid.innerHTML = grid;

  // 标注媒体
  const media = job.files && job.files.media;
  if (media) {
    els.mediaWrap.hidden = false;
    if (isVdo) els.mediaViewer.innerHTML = `<video controls preload="metadata" src="${esc(media)}"></video>`;
    else els.mediaViewer.innerHTML = `<img src="${esc(media)}" alt="标注结果" />`;
  } else {
    els.mediaWrap.hidden = true;
    els.mediaViewer.innerHTML = "";
  }

  // 看板
  if (job.files && job.files.dashboard) {
    els.dashImg.src = job.files.dashboard;
  }

  // 操作按钮
  els.rActions.innerHTML = "";
  const addBtn = (label, cls, url, isFile) => {
    const a = document.createElement("a");
    a.className = "btn " + cls;
    a.textContent = label;
    a.href = url;
    if (isFile) { a.target = "_blank"; a.rel = "noopener"; }
    els.rActions.appendChild(a);
  };
  if (job.files && job.files.report) addBtn("下载报告", "btn-ghost", job.files.report, true);
  if (job.files && job.files.media) addBtn("查看标注", "btn-ghost", job.files.media, true);

  // 报告文本
  els.reportText.textContent = "加载中…";
  fetch(`/api/jobs/${job.id}/report`)
    .then((r) => (r.ok ? r.text() : "（报告不可用）"))
    .then((txt) => { if (activeResultJobId === job.id) els.reportText.textContent = txt; })
    .catch(() => { els.reportText.textContent = "（报告加载失败）"; });
}

function renderError(job) {
  els.progressCard.hidden = false;
  renderProgress(job);
  els.resultCard.hidden = true;
  toast("任务失败：" + (job.error || "未知错误"));
}

/* ---------------- 历史 ---------------- */
async function refreshHistory() {
  try {
    const { jobs } = await api("/api/jobs");
    renderHistory(jobs);
  } catch (e) {
    toast("加载历史失败：" + e.message);
  }
}

function renderHistory(jobs) {
  if (!jobs || jobs.length === 0) {
    els.historyList.innerHTML = '<li class="history-empty">暂无历史记录，上传文件开始分析</li>';
    return;
  }
  els.historyList.innerHTML = "";
  jobs.forEach((job) => {
    const li = document.createElement("li");
    li.className = "history-item" + (job.id === activeResultJobId ? " active" : "");
    const s = job.summary || {};
    const metricLine =
      job.status === "done"
        ? `估算 ${s.unique_students ?? 0} 人 · 均专注 ${Number(s.avg_attention || 0).toFixed(0)}%`
        : statusText(job.status);
    const p = Math.max(0, Math.min(100, Math.round(job.progress || 0)));
    const kind = job.file_kind === "video" ? "视频" : "图片";
    li.innerHTML = `
      <div class="h-top">
        <span class="h-name">${esc(job.filename)}</span>
        <span class="badge ${job.status}">${statusText(job.status)}</span>
      </div>
      <div class="h-meta">${kind} · ${fmtTime(job.created_at)}</div>
      <div class="h-metric">${esc(metricLine)}</div>
      ${job.status === "running" || job.status === "pending"
        ? `<div class="progress-track h-progress"><div class="progress-fill" style="width:${p}%"></div></div>`
        : ""}`;
    li.addEventListener("click", () => {
      activeResultJobId = job.id;
      [...els.historyList.children].forEach((c) => c.classList.remove("active"));
      li.classList.add("active");
      openHistoryJob(job);
    });
    els.historyList.appendChild(li);
  });
}

function openHistoryJob(job) {
  els.resultCard.hidden = true;
  els.progressCard.hidden = false;
  if (job.status === "done") {
    renderProgress(job);
    renderResult(job);
  } else if (job.status === "error") {
    renderError(job);
  } else {
    renderProgress(job);
    startPoll(job.id);
  }
}

/* ---------------- 启动 ---------------- */
bindUpload();
checkHealth();
refreshHistory();
setInterval(checkHealth, 15000);
