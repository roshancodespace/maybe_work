let state = {
  devices: [],
  activeSerial: null,
  activeStatus: null,
  workflows: {},
  currentWfId: null,
  scheduler: {
    items: [],
    inter_repetition_delay: 2.0,
    inter_workflow_delay: 4.0,
    cooldown_interval: 3,
    cooldown_duration: 8.0,
    max_execution_duration: 900
  },
  progress: {
    state: "idle",
    active_device: null,
    current_workflow_id: null,
    current_workflow_name: null,
    current_task_index: 0,
    total_tasks: 0,
    current_task_name: null,
    current_rep: 0,
    total_reps: 0,
    current_queue_index: 0,
    total_queue_items: 0,
    elapsed_seconds: 0.0,
    error_message: null
  },
  logs: []
};

// DOM References
const el = {
  deviceSelect: document.getElementById("deviceSelect"),
  deviceStatusBadge: document.getElementById("deviceStatusBadge"),
  deviceSpecs: document.getElementById("deviceSpecs"),
  stateDot: document.getElementById("stateDot"),
  stateLabel: document.getElementById("stateLabel"),
  btnStart: document.getElementById("btnStart"),
  btnPause: document.getElementById("btnPause"),
  btnResume: document.getElementById("btnResume"),
  btnStop: document.getElementById("btnStop"),
  runDurationSelect: document.getElementById("runDurationSelect"),

  tabBtnScheduler: document.getElementById("tabBtnScheduler"),
  tabBtnWorkflows: document.getElementById("tabBtnWorkflows"),
  tabContentScheduler: document.getElementById("tabContentScheduler"),
  tabContentWorkflows: document.getElementById("tabContentWorkflows"),

  queueList: document.getElementById("queueList"),
  btnAddQueueItem: document.getElementById("btnAddQueueItem"),
  interRepDelay: document.getElementById("interRepDelay"),
  interWfDelay: document.getElementById("interWfDelay"),
  cooldownInterval: document.getElementById("cooldownInterval"),
  cooldownDuration: document.getElementById("cooldownDuration"),
  maxDuration: document.getElementById("maxDuration"),
  btnSaveScheduler: document.getElementById("btnSaveScheduler"),

  wfSelect: document.getElementById("wfSelect"),
  btnNewWorkflow: document.getElementById("btnNewWorkflow"),
  btnDuplicateWorkflow: document.getElementById("btnDuplicateWorkflow"),
  btnDeleteWorkflow: document.getElementById("btnDeleteWorkflow"),
  wfName: document.getElementById("wfName"),
  wfDesc: document.getElementById("wfDesc"),
  wfPreset: document.getElementById("wfPreset"),
  wfRepetitions: document.getElementById("wfRepetitions"),
  randDelayMin: document.getElementById("randDelayMin"),
  randDelayMax: document.getElementById("randDelayMax"),
  randScrollMin: document.getElementById("randScrollMin"),
  randScrollMax: document.getElementById("randScrollMax"),
  randPauseChance: document.getElementById("randPauseChance"),
  randWiggleEnabled: document.getElementById("randWiggleEnabled"),
  taskCount: document.getElementById("taskCount"),
  taskList: document.getElementById("taskList"),
  btnAddTask: document.getElementById("btnAddTask"),
  btnSaveWorkflow: document.getElementById("btnSaveWorkflow"),

  metricCurrentWf: document.getElementById("metricCurrentWf"),
  metricCurrentTask: document.getElementById("metricCurrentTask"),
  metricRep: document.getElementById("metricRep"),
  metricQueue: document.getElementById("metricQueue"),
  metricElapsed: document.getElementById("metricElapsed"),

  deviceScreenImg: document.getElementById("deviceScreenImg"),
  screenTapIndicator: document.getElementById("screenTapIndicator"),
  screenDimensions: document.getElementById("screenDimensions"),
  btnRefreshScreen: document.getElementById("btnRefreshScreen"),
  autoRefreshToggle: document.getElementById("autoRefreshToggle"),
  btnDeviceBack: document.getElementById("btnDeviceBack"),
  btnDeviceHome: document.getElementById("btnDeviceHome"),

  activityLog: document.getElementById("activityLog"),
  logAutoScroll: document.getElementById("logAutoScroll"),
  btnClearLogs: document.getElementById("btnClearLogs"),

  taskModal: document.getElementById("taskModal"),
  taskModalTitle: document.getElementById("taskModalTitle"),
  btnModalClose: document.getElementById("btnModalClose"),
  btnModalCancel: document.getElementById("btnModalCancel"),
  btnModalSave: document.getElementById("btnModalSave"),
  editTaskId: document.getElementById("editTaskId"),
  taskNameInput: document.getElementById("taskNameInput"),
  taskTypeSelect: document.getElementById("taskTypeSelect"),
  taskParamsContainer: document.getElementById("taskParamsContainer"),
  taskOnFailure: document.getElementById("taskOnFailure"),
  taskRetries: document.getElementById("taskRetries")
};

// Initialization
async function init() {
  bindEvents();
  await refreshDevices();
  await loadWorkflows();
  await loadScheduler();
  await loadStatus();
  await loadLogs();
  initWebSocket();
  startScreenRefreshLoop();
}

function bindEvents() {
  // Tabs
  el.tabBtnScheduler.addEventListener("click", () => switchTab("scheduler"));
  el.tabBtnWorkflows.addEventListener("click", () => switchTab("workflows"));

  // Device select
  el.deviceSelect.addEventListener("change", async (e) => {
    await fetch("/api/devices/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ serial: e.target.value })
    });
    await refreshDevices();
  });

  // Controls
  el.btnStart.addEventListener("click", handleStart);
  el.btnPause.addEventListener("click", handlePause);
  el.btnResume.addEventListener("click", handleResume);
  el.btnStop.addEventListener("click", handleStop);

  // Scheduler
  el.btnAddQueueItem.addEventListener("click", handleAddQueueItem);
  el.btnSaveScheduler.addEventListener("click", handleSaveScheduler);

  // Workflows
  el.wfSelect.addEventListener("change", (e) => selectWorkflow(e.target.value));
  el.btnNewWorkflow.addEventListener("click", handleNewWorkflow);
  el.btnDuplicateWorkflow.addEventListener("click", handleDuplicateWorkflow);
  el.btnDeleteWorkflow.addEventListener("click", handleDeleteWorkflow);
  el.btnSaveWorkflow.addEventListener("click", handleSaveWorkflow);
  el.btnAddTask.addEventListener("click", () => openTaskModal());

  // Task Modal
  el.btnModalClose.addEventListener("click", closeTaskModal);
  el.btnModalCancel.addEventListener("click", closeTaskModal);
  el.btnModalSave.addEventListener("click", saveTaskModal);
  el.taskTypeSelect.addEventListener("change", () => renderTaskParamInputs());

  // Screen interactive tap & buttons
  el.deviceScreenImg.addEventListener("click", handleScreenClick);
  el.btnRefreshScreen.addEventListener("click", () => refreshScreenshot(true));
  el.btnDeviceBack.addEventListener("click", () => sendDeviceKey("BACK"));
  el.btnDeviceHome.addEventListener("click", () => sendDeviceKey("HOME"));

  // Log controls
  el.btnClearLogs.addEventListener("click", async () => {
    await fetch("/api/logs", { method: "DELETE" });
    el.activityLog.innerHTML = "";
    state.logs = [];
  });
}

function switchTab(tab) {
  if (tab === "scheduler") {
    el.tabBtnScheduler.classList.add("active");
    el.tabBtnWorkflows.classList.remove("active");
    el.tabContentScheduler.classList.add("active");
    el.tabContentWorkflows.classList.remove("active");
  } else {
    el.tabBtnScheduler.classList.remove("active");
    el.tabBtnWorkflows.classList.add("active");
    el.tabContentScheduler.classList.remove("active");
    el.tabContentWorkflows.classList.add("active");
  }
}

// Devices
async function refreshDevices() {
  try {
    const res = await fetch("/api/devices");
    const data = await res.json();
    state.devices = data.devices || [];
    state.activeSerial = data.active_serial;
    state.activeStatus = data.active_status;

    el.deviceSelect.innerHTML = "";
    if (state.devices.length === 0) {
      el.deviceSelect.innerHTML = `<option value="">No devices found</option>`;
      el.deviceStatusBadge.textContent = "Offline";
      el.deviceStatusBadge.className = "status-tag tag-offline";
      el.deviceSpecs.textContent = "";
    } else {
      state.devices.forEach((d) => {
        const opt = document.createElement("option");
        opt.value = d.serial;
        opt.textContent = `${d.model} (${d.serial})`;
        if (d.serial === state.activeSerial) opt.selected = true;
        el.deviceSelect.appendChild(opt);
      });
      if (state.activeStatus) {
        el.deviceStatusBadge.textContent = state.activeStatus.connected ? "Connected" : "Offline";
        el.deviceStatusBadge.className = state.activeStatus.connected ? "status-tag tag-online" : "status-tag tag-offline";
        el.deviceSpecs.textContent = `${state.activeStatus.width}x${state.activeStatus.height} • ${state.activeStatus.battery_level ?? '—'}% battery • ${state.activeStatus.transport_type}`;
        el.screenDimensions.textContent = `${state.activeStatus.width}x${state.activeStatus.height}`;
      }
    }
  } catch (err) {
    console.error("Failed to load devices", err);
  }
}

// Workflows
async function loadWorkflows() {
  try {
    const res = await fetch("/api/workflows");
    const list = await res.json();
    state.workflows = {};
    el.wfSelect.innerHTML = "";

    list.forEach((wf) => {
      state.workflows[wf.id] = wf;
      const opt = document.createElement("option");
      opt.value = wf.id;
      opt.textContent = wf.name;
      el.wfSelect.appendChild(opt);
    });

    if (!state.currentWfId && list.length > 0) {
      state.currentWfId = list[0].id;
    }

    if (state.currentWfId && state.workflows[state.currentWfId]) {
      el.wfSelect.value = state.currentWfId;
      selectWorkflow(state.currentWfId);
    }
  } catch (err) {
    console.error("Failed to load workflows", err);
  }
}

function selectWorkflow(wfId) {
  state.currentWfId = wfId;
  const wf = state.workflows[wfId];
  if (!wf) return;

  el.wfName.value = wf.name || "";
  el.wfDesc.value = wf.description || "";
  el.wfPreset.value = wf.preset || "natural";
  el.wfRepetitions.value = wf.repetitions || 1;

  const r = wf.randomization || {};
  el.randDelayMin.value = r.min_delay ?? 1.0;
  el.randDelayMax.value = r.max_delay ?? 2.5;
  el.randScrollMin.value = r.min_scroll_pct ?? 0.3;
  el.randScrollMax.value = r.max_scroll_pct ?? 0.65;
  el.randPauseChance.value = Math.round((r.reading_pause_chance ?? 0.25) * 100);
  el.randWiggleEnabled.checked = r.wiggle_enabled ?? true;

  renderTaskList(wf.tasks || []);
}

function renderTaskList(tasks) {
  el.taskCount.textContent = tasks.length;
  el.taskList.innerHTML = "";

  tasks.forEach((t, index) => {
    const item = document.createElement("div");
    item.className = "task-row";
    item.innerHTML = `
      <div class="task-row-main">
        <span class="index-badge">${index + 1}</span>
        <span class="task-type-badge">${t.action_type.replace(/_/g, ' ')}</span>
        <span class="task-name-text">${escapeHtml(t.name)}</span>
      </div>
      <div class="task-row-actions">
        <button class="btn btn-xs btn-secondary btn-move-up" data-idx="${index}" ${index === 0 ? "disabled" : ""}>Up</button>
        <button class="btn btn-xs btn-secondary btn-move-down" data-idx="${index}" ${index === tasks.length - 1 ? "disabled" : ""}>Down</button>
        <button class="btn btn-xs btn-secondary btn-edit-task" data-idx="${index}">Edit</button>
        <button class="btn btn-xs btn-danger-text btn-del-task" data-idx="${index}">Remove</button>
      </div>
    `;
    el.taskList.appendChild(item);
  });

  // Attach button events
  el.taskList.querySelectorAll(".btn-move-up").forEach((b) => {
    b.addEventListener("click", () => moveTask(parseInt(b.dataset.idx), -1));
  });
  el.taskList.querySelectorAll(".btn-move-down").forEach((b) => {
    b.addEventListener("click", () => moveTask(parseInt(b.dataset.idx), 1));
  });
  el.taskList.querySelectorAll(".btn-edit-task").forEach((b) => {
    b.addEventListener("click", () => openTaskModal(parseInt(b.dataset.idx)));
  });
  el.taskList.querySelectorAll(".btn-del-task").forEach((b) => {
    b.addEventListener("click", () => deleteTask(parseInt(b.dataset.idx)));
  });
}

function moveTask(index, offset) {
  const wf = state.workflows[state.currentWfId];
  if (!wf) return;
  const target = index + offset;
  if (target < 0 || target >= wf.tasks.length) return;
  const temp = wf.tasks[index];
  wf.tasks[index] = wf.tasks[target];
  wf.tasks[target] = temp;
  renderTaskList(wf.tasks);
}

function deleteTask(index) {
  const wf = state.workflows[state.currentWfId];
  if (!wf) return;
  wf.tasks.splice(index, 1);
  renderTaskList(wf.tasks);
}

async function handleSaveWorkflow() {
  const wf = state.workflows[state.currentWfId];
  if (!wf) return;

  wf.name = el.wfName.value.trim() || "Untitled Workflow";
  wf.description = el.wfDesc.value.trim();
  wf.preset = el.wfPreset.value;
  wf.repetitions = parseInt(el.wfRepetitions.value) || 1;

  wf.randomization = {
    min_delay: parseFloat(el.randDelayMin.value) || 1.0,
    max_delay: parseFloat(el.randDelayMax.value) || 2.5,
    min_scroll_pct: parseFloat(el.randScrollMin.value) || 0.3,
    max_scroll_pct: parseFloat(el.randScrollMax.value) || 0.65,
    swipe_duration_min: 200,
    swipe_duration_max: 400,
    wiggle_enabled: el.randWiggleEnabled.checked,
    wiggle_chance: 0.35,
    reading_pause_chance: (parseInt(el.randPauseChance.value) || 25) / 100,
    reading_pause_min: 2.0,
    reading_pause_max: 5.0,
    explore_result_variation: true
  };

  try {
    const res = await fetch(`/api/workflows/${wf.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(wf)
    });
    if (res.ok) {
      await loadWorkflows();
      renderQueueList();
    }
  } catch (err) {
    alert("Error saving workflow: " + err);
  }
}

async function handleNewWorkflow() {
  const id = "wf-" + Date.now();
  const newWf = {
    id: id,
    name: "New Custom Workflow",
    description: "",
    preset: "natural",
    repetitions: 1,
    tasks: []
  };
  try {
    const res = await fetch("/api/workflows", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newWf)
    });
    if (res.ok) {
      state.currentWfId = id;
      await loadWorkflows();
    }
  } catch (err) {
    alert("Error creating workflow: " + err);
  }
}

async function handleDuplicateWorkflow() {
  if (!state.currentWfId) return;
  try {
    const res = await fetch(`/api/workflows/${state.currentWfId}/duplicate`, { method: "POST" });
    if (res.ok) {
      const copy = await res.json();
      state.currentWfId = copy.id;
      await loadWorkflows();
    }
  } catch (err) {
    alert("Error duplicating workflow: " + err);
  }
}

async function handleDeleteWorkflow() {
  if (!state.currentWfId) return;
  if (!confirm(`Delete workflow '${state.workflows[state.currentWfId]?.name}'?`)) return;
  try {
    await fetch(`/api/workflows/${state.currentWfId}`, { method: "DELETE" });
    state.currentWfId = null;
    await loadWorkflows();
    await loadScheduler();
  } catch (err) {
    alert("Error deleting workflow: " + err);
  }
}

// Task Modal
function openTaskModal(taskIndex = null) {
  const wf = state.workflows[state.currentWfId];
  if (!wf) return;

  if (taskIndex !== null && wf.tasks[taskIndex]) {
    const t = wf.tasks[taskIndex];
    el.taskModalTitle.textContent = "Edit Task";
    el.editTaskId.value = String(taskIndex);
    el.taskNameInput.value = t.name;
    el.taskTypeSelect.value = t.action_type;
    el.taskOnFailure.value = t.on_failure || "continue";
    el.taskRetries.value = t.retries || 1;
    renderTaskParamInputs(t.params);
  } else {
    el.taskModalTitle.textContent = "Add Task";
    el.editTaskId.value = "";
    el.taskNameInput.value = "New Action";
    el.taskTypeSelect.value = "human_scroll";
    el.taskOnFailure.value = "continue";
    el.taskRetries.value = 1;
    renderTaskParamInputs();
  }

  el.taskModal.classList.add("open");
}

function closeTaskModal() {
  el.taskModal.classList.remove("open");
}

function renderTaskParamInputs(params = {}) {
  const type = el.taskTypeSelect.value;
  let html = "";

  if (type === "open_url") {
    html = `
      <div class="field-group">
        <label>URL to open</label>
        <input type="text" id="param_url" class="form-input" value="${escapeHtml(params.url || "https://github.com/explore")}">
      </div>
    `;
  } else if (type === "search_topic") {
    html = `
      <div class="field-group">
        <label>Search Query / Topic</label>
        <input type="text" id="param_topic" class="form-input" value="${escapeHtml(params.topic || "flutter")}">
      </div>
      <div class="field-group">
        <label>URL Template ({query} placeholder)</label>
        <input type="text" id="param_url_template" class="form-input" value="${escapeHtml(params.url_template || "https://github.com/search?q={query}&type=repositories")}">
      </div>
    `;
  } else if (type === "human_scroll") {
    html = `
      <div class="form-grid">
        <div class="field-group">
          <label>Direction</label>
          <select id="param_direction" class="form-select">
            <option value="down" ${params.direction !== "up" ? "selected" : ""}>Down</option>
            <option value="up" ${params.direction === "up" ? "selected" : ""}>Up</option>
          </select>
        </div>
        <div class="field-group">
          <label>Distance (% screen height)</label>
          <input type="number" id="param_distance_pct" class="form-input" min="0.1" max="0.9" step="0.05" value="${params.distance_pct ?? 0.5}">
        </div>
      </div>
    `;
  } else if (type === "tap_element") {
    html = `
      <div class="field-group">
        <label>Element Query (Text / Content description)</label>
        <input type="text" id="param_query" class="form-input" value="${escapeHtml(params.query || "")}" placeholder="e.g. flutter/flutter or Readme">
      </div>
      <div class="form-grid">
        <div class="field-group">
          <label>Match By</label>
          <select id="param_match_by" class="form-select">
            <option value="text" ${params.match_by === "text" ? "selected" : ""}>Text</option>
            <option value="desc" ${params.match_by === "desc" ? "selected" : ""}>Accessibility description</option>
            <option value="id" ${params.match_by === "id" ? "selected" : ""}>Resource ID</option>
            <option value="any" ${params.match_by === "any" ? "selected" : ""}>Any attribute</option>
          </select>
        </div>
        <div class="field-group">
          <label>Fallback Coordinates (relative X, Y)</label>
          <div class="input-range">
            <input type="number" id="param_fb_x" class="form-input" step="0.05" value="${params.fallback_x ?? 0.5}">
            <input type="number" id="param_fb_y" class="form-input" step="0.05" value="${params.fallback_y ?? 0.5}">
          </div>
        </div>
      </div>
    `;
  } else if (type === "find_and_click_more") {
    html = `
      <div class="field-group">
        <label>Max scroll attempts while locating 'More' button</label>
        <input type="number" id="param_max_scrolls" class="form-input" min="1" max="25" value="${params.max_scroll_attempts || 8}">
      </div>
      <p class="section-subtext">Scrolls down with humanized wiggles until a button labeled 'More' or 'Load more' appears, then clicks it to load additional feed content.</p>
    `;
  } else if (type === "tap_coords") {
    html = `
      <div class="form-grid">
        <div class="field-group">
          <label>X (Normalized 0.0-1.0 or pixel)</label>
          <input type="number" id="param_x" class="form-input" step="0.01" value="${params.x ?? 0.5}">
        </div>
        <div class="field-group">
          <label>Y (Normalized 0.0-1.0 or pixel)</label>
          <input type="number" id="param_y" class="form-input" step="0.01" value="${params.y ?? 0.5}">
        </div>
      </div>
    `;
  } else if (type === "enter_text") {
    html = `
      <div class="field-group">
        <label>Text to type</label>
        <input type="text" id="param_text" class="form-input" value="${escapeHtml(params.text || "")}">
      </div>
      <div class="field-group">
        <label class="clean-checkbox">
          <input type="checkbox" id="param_press_enter" ${params.press_enter ? "checked" : ""}>
          <span>Send Enter key after typing</span>
        </label>
      </div>
    `;
  } else if (type === "press_key") {
    html = `
      <div class="field-group">
        <label>Key code or name</label>
        <input type="text" id="param_key" class="form-input" value="${escapeHtml(params.key || "ENTER")}" placeholder="e.g. BACK, HOME, ENTER, TAB">
      </div>
    `;
  } else if (type === "wait_inspect") {
    html = `
      <div class="field-group">
        <label>Wait duration (seconds)</label>
        <input type="number" id="param_seconds" class="form-input" min="0.5" step="0.5" value="${params.seconds ?? 2.0}">
      </div>
    `;
  } else if (type === "launch_app") {
    html = `
      <div class="field-group">
        <label>Application package name</label>
        <input type="text" id="param_pkg" class="form-input" value="${escapeHtml(params.package || "com.android.chrome")}">
      </div>
    `;
  } else if (type === "cooldown") {
    html = `
      <div class="field-group">
        <label>Cooldown duration (seconds)</label>
        <input type="number" id="param_cd_seconds" class="form-input" min="1" step="1" value="${params.seconds ?? 5.0}">
      </div>
    `;
  } else {
    html = `<p class="section-subtext">No additional parameters required for this action.</p>`;
  }

  el.taskParamsContainer.innerHTML = html;
}

function saveTaskModal() {
  const wf = state.workflows[state.currentWfId];
  if (!wf) return;

  const type = el.taskTypeSelect.value;
  const name = el.taskNameInput.value.trim() || type;
  const params = {};

  if (type === "open_url") {
    params.url = document.getElementById("param_url")?.value || "";
  } else if (type === "search_topic") {
    params.topic = document.getElementById("param_topic")?.value || "";
    params.url_template = document.getElementById("param_url_template")?.value || "";
  } else if (type === "human_scroll") {
    params.direction = document.getElementById("param_direction")?.value || "down";
    params.distance_pct = parseFloat(document.getElementById("param_distance_pct")?.value) || 0.5;
  } else if (type === "tap_element") {
    params.query = document.getElementById("param_query")?.value || "";
    params.match_by = document.getElementById("param_match_by")?.value || "text";
    const fbx = parseFloat(document.getElementById("param_fb_x")?.value);
    const fby = parseFloat(document.getElementById("param_fb_y")?.value);
    if (!isNaN(fbx) && !isNaN(fby)) {
      params.fallback_x = fbx;
      params.fallback_y = fby;
    }
  } else if (type === "find_and_click_more") {
    params.max_scroll_attempts = parseInt(document.getElementById("param_max_scrolls")?.value) || 8;
  } else if (type === "tap_coords") {
    params.x = parseFloat(document.getElementById("param_x")?.value) || 0.5;
    params.y = parseFloat(document.getElementById("param_y")?.value) || 0.5;
  } else if (type === "enter_text") {
    params.text = document.getElementById("param_text")?.value || "";
    params.press_enter = document.getElementById("param_press_enter")?.checked || false;
  } else if (type === "press_key") {
    params.key = document.getElementById("param_key")?.value || "ENTER";
  } else if (type === "wait_inspect") {
    params.seconds = parseFloat(document.getElementById("param_seconds")?.value) || 2.0;
  } else if (type === "launch_app") {
    params.package = document.getElementById("param_pkg")?.value || "com.android.chrome";
  } else if (type === "cooldown") {
    params.seconds = parseFloat(document.getElementById("param_cd_seconds")?.value) || 5.0;
  }

  const editIndex = el.editTaskId.value !== "" ? parseInt(el.editTaskId.value) : null;
  const taskObj = {
    id: editIndex !== null ? wf.tasks[editIndex].id : "task-" + Date.now(),
    name: name,
    action_type: type,
    params: params,
    enabled: true,
    on_failure: el.taskOnFailure.value,
    retries: parseInt(el.taskRetries.value) || 1
  };

  if (editIndex !== null) {
    wf.tasks[editIndex] = taskObj;
  } else {
    wf.tasks.push(taskObj);
  }

  renderTaskList(wf.tasks);
  closeTaskModal();
}

// Scheduler
async function loadScheduler() {
  try {
    const res = await fetch("/api/scheduler");
    state.scheduler = await res.json();
    el.interRepDelay.value = state.scheduler.inter_repetition_delay ?? 2.0;
    el.interWfDelay.value = state.scheduler.inter_workflow_delay ?? 4.0;
    el.cooldownInterval.value = state.scheduler.cooldown_interval ?? 3;
    el.cooldownDuration.value = state.scheduler.cooldown_duration ?? 8.0;
    el.maxDuration.value = state.scheduler.max_execution_duration ?? 900;
    renderQueueList();
  } catch (err) {
    console.error("Failed to load scheduler", err);
  }
}

function renderQueueList() {
  el.queueList.innerHTML = "";
  if (!state.scheduler.items || state.scheduler.items.length === 0) {
    el.queueList.innerHTML = `<div class="queue-row" style="color:var(--text-muted)">Queue is empty. Click '+ Add Workflow'.</div>`;
    return;
  }

  state.scheduler.items.forEach((item, index) => {
    const wf = state.workflows[item.workflow_id];
    const wfName = wf ? wf.name : item.workflow_id;
    const div = document.createElement("div");
    div.className = "queue-row";
    div.innerHTML = `
      <div class="queue-row-info">
        <span class="index-badge">${index + 1}</span>
        <span class="queue-row-title">${escapeHtml(wfName)}</span>
      </div>
      <div class="queue-row-actions">
        <span class="task-type-badge">Non-stop</span>
        <button class="btn btn-xs btn-tonal btn-queue-up" data-idx="${index}" ${index === 0 ? "disabled" : ""}>Up</button>
        <button class="btn btn-xs btn-tonal btn-queue-down" data-idx="${index}" ${index === state.scheduler.items.length - 1 ? "disabled" : ""}>Down</button>
        <button class="btn btn-xs btn-text-danger btn-queue-del" data-idx="${index}">Remove</button>
      </div>
    `;
    el.queueList.appendChild(div);
  });

  el.queueList.querySelectorAll(".btn-queue-up").forEach((b) => {
    b.addEventListener("click", () => moveQueueItem(parseInt(b.dataset.idx), -1));
  });
  el.queueList.querySelectorAll(".btn-queue-down").forEach((b) => {
    b.addEventListener("click", () => moveQueueItem(parseInt(b.dataset.idx), 1));
  });
  el.queueList.querySelectorAll(".btn-queue-del").forEach((b) => {
    b.addEventListener("click", () => deleteQueueItem(parseInt(b.dataset.idx)));
  });
}

function moveQueueItem(idx, offset) {
  const target = idx + offset;
  if (target < 0 || target >= state.scheduler.items.length) return;
  const temp = state.scheduler.items[idx];
  state.scheduler.items[idx] = state.scheduler.items[target];
  state.scheduler.items[target] = temp;
  renderQueueList();
}

function deleteQueueItem(idx) {
  state.scheduler.items.splice(idx, 1);
  renderQueueList();
}

function handleAddQueueItem() {
  const keys = Object.keys(state.workflows);
  if (keys.length === 0) {
    alert("No workflows available. Please create a workflow first.");
    return;
  }
  const chosenId = state.currentWfId || keys[0];
  state.scheduler.items.push({
    workflow_id: chosenId,
    repetitions: 1
  });
  renderQueueList();
}

async function handleSaveScheduler() {
  state.scheduler.inter_repetition_delay = parseFloat(el.interRepDelay.value) || 2.0;
  state.scheduler.inter_workflow_delay = parseFloat(el.interWfDelay.value) || 4.0;
  state.scheduler.cooldown_interval = parseInt(el.cooldownInterval.value) || 3;
  state.scheduler.cooldown_duration = parseFloat(el.cooldownDuration.value) || 8.0;
  const maxD = parseFloat(el.maxDuration.value);
  state.scheduler.max_execution_duration = (maxD && maxD > 0) ? maxD : null;

  try {
    await fetch("/api/scheduler", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.scheduler)
    });
  } catch (err) {
    alert("Error saving scheduler: " + err);
  }
}

// Execution Controls
async function handleStart() {
  const durVal = parseFloat(el.runDurationSelect ? el.runDurationSelect.value : "0") || 0;
  state.scheduler.duration_minutes = durVal;
  state.scheduler.max_execution_duration = durVal > 0 ? (durVal * 60) : null;
  state.scheduler.inter_repetition_delay = parseFloat(el.interRepDelay.value) || 1.5;
  state.scheduler.inter_workflow_delay = parseFloat(el.interWfDelay.value) || 3.0;
  state.scheduler.cooldown_interval = 0;
  state.scheduler.cooldown_duration = 0;

  try {
    const res = await fetch("/api/control/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.scheduler)
    });
    if (!res.ok) {
      const err = await res.json();
      alert("Failed to start: " + (err.detail || "Unknown error"));
    }
  } catch (err) {
    alert("Error starting automation: " + err);
  }
}

async function handlePause() {
  try {
    await fetch("/api/control/pause", { method: "POST" });
  } catch (err) {
    console.error("Pause failed", err);
  }
}

async function handleResume() {
  try {
    await fetch("/api/control/resume", { method: "POST" });
  } catch (err) {
    console.error("Resume failed", err);
  }
}

async function handleStop() {
  try {
    await fetch("/api/control/stop", { method: "POST" });
  } catch (err) {
    console.error("Stop failed", err);
  }
}

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    updateProgressUI(data.progress);
  } catch (err) {
    console.error("Status load failed", err);
  }
}

function updateProgressUI(p) {
  if (!p) return;
  state.progress = p;

  const s = p.state || "idle";
  el.stateLabel.textContent = s.toUpperCase();
  el.stateDot.className = "status-indicator-dot " + s;

  if (s === "running") {
    el.btnStart.disabled = true;
    el.btnPause.disabled = false;
    el.btnPause.style.display = "inline-flex";
    el.btnResume.style.display = "none";
    el.btnStop.disabled = false;
  } else if (s === "paused") {
    el.btnStart.disabled = true;
    el.btnPause.style.display = "none";
    el.btnResume.style.display = "inline-flex";
    el.btnResume.disabled = false;
    el.btnStop.disabled = false;
  } else {
    el.btnStart.disabled = false;
    el.btnPause.disabled = true;
    el.btnPause.style.display = "inline-flex";
    el.btnResume.style.display = "none";
    el.btnStop.disabled = true;
  }

  el.metricCurrentWf.textContent = p.current_workflow_name || "—";
  el.metricCurrentTask.textContent = p.current_task_name ? `${p.current_task_index}/${p.total_tasks} - ${p.current_task_name}` : "—";
  el.metricRep.textContent = `Cycle ${p.current_rep || 0}`;
  el.metricQueue.textContent = (p.duration_minutes && p.duration_minutes > 0) ? `${p.duration_minutes}m limit` : "Infinite (Non-stop)";
  el.metricElapsed.textContent = `${p.elapsed_seconds.toFixed(1)}s`;
}

// Activity Logs
async function loadLogs() {
  try {
    const res = await fetch("/api/logs");
    const list = await res.json();
    state.logs = list || [];
    renderLogs(state.logs);
  } catch (err) {
    console.error("Logs load failed", err);
  }
}

function renderLogs(logs) {
  el.activityLog.innerHTML = "";
  logs.forEach((log) => {
    appendLogLine(log);
  });
  if (el.logAutoScroll.checked) {
    el.activityLog.scrollTop = el.activityLog.scrollHeight;
  }
}

function appendLogLine(log) {
  const line = document.createElement("div");
  line.className = `log-entry level-${log.level}`;
  line.innerHTML = `
    <span class="log-time">[${escapeHtml(log.timestamp)}]</span>
    <span class="log-body">${escapeHtml(log.message)}</span>
  `;
  el.activityLog.appendChild(line);
}

// Live Device Screenshot Feed
let isRefreshingScreen = false;
function refreshScreenshot(force = false) {
  if (isRefreshingScreen && !force) return;
  isRefreshingScreen = true;

  const img = new Image();
  const url = `/api/device/screenshot?t=${Date.now()}`;
  img.onload = () => {
    el.deviceScreenImg.src = url;
    isRefreshingScreen = false;
  };
  img.onerror = () => {
    isRefreshingScreen = false;
  };
  img.src = url;
}

function startScreenRefreshLoop() {
  setInterval(() => {
    if (el.autoRefreshToggle.checked) {
      refreshScreenshot(false);
    }
  }, 1800);
}

// Direct interactive click on device screen
async function handleScreenClick(e) {
  const rect = el.deviceScreenImg.getBoundingClientRect();
  const clickX = e.clientX - rect.left;
  const clickY = e.clientY - rect.top;

  const relX = clickX / rect.width;
  const relY = clickY / rect.height;

  // Visual tap indicator
  el.screenTapIndicator.style.left = `${clickX + el.deviceScreenImg.offsetLeft}px`;
  el.screenTapIndicator.style.top = `${clickY + el.deviceScreenImg.offsetTop}px`;
  el.screenTapIndicator.style.display = "block";
  setTimeout(() => {
    el.screenTapIndicator.style.display = "none";
  }, 350);

  try {
    await fetch("/api/device/tap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ x: relX, y: relY })
    });
    setTimeout(() => refreshScreenshot(true), 400);
  } catch (err) {
    console.error("Tap failed", err);
  }
}

async function sendDeviceKey(key) {
  try {
    await fetch("/api/device/key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: key })
    });
    setTimeout(() => refreshScreenshot(true), 500);
  } catch (err) {
    console.error("Key event failed", err);
  }
}

// WebSocket Connection
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  let ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log("WebSocket connected");
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "init" || data.type === "update") {
        if (data.progress) {
          updateProgressUI(data.progress);
        }
        if (data.recent_logs && data.recent_logs.length > 0) {
          const existingTimestamps = new Set(state.logs.map(l => l.timestamp + l.message));
          data.recent_logs.forEach((log) => {
            const key = log.timestamp + log.message;
            if (!existingTimestamps.has(key)) {
              state.logs.push(log);
              appendLogLine(log);
              existingTimestamps.add(key);
            }
          });
          if (el.logAutoScroll.checked) {
            el.activityLog.scrollTop = el.activityLog.scrollHeight;
          }
        }
      }
    } catch (e) {
      console.error("WS message parse error", e);
    }
  };

  ws.onclose = () => {
    setTimeout(initWebSocket, 2000);
  };
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", init);
