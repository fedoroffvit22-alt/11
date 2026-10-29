const casesNode = document.querySelector("#cases");
const deskNode = document.querySelector("#desk");
const coachNode = document.querySelector("#coach");
const noteNode = document.querySelector("#import-note");
const exportNode = document.querySelector("#export");
const formNode = document.querySelector("#import-form");
const fileNode = document.querySelector("#file");

const LEVEL_LABEL = { basic: "базовый", medium: "средний", hard: "сложный" };

let library = { cases: [], learned: [] };
let journal = [];
let session = null;
let busy = false;
let timer = 0;

formNode.addEventListener("submit", (event) => {
  event.preventDefault();
  importText(exportNode.value);
});

document.querySelector("#focus").addEventListener("change", () => {
  renderCases();
});

document.querySelector("#examples").addEventListener("click", async () => {
  await run(async () => {
    const data = await api("/api/examples", { method: "POST", body: "{}" });
    applyLibrary(data, `Учебных звонков в библиотеке: ${data.cases.length}.`);
  });
});

fileNode.addEventListener("change", async () => {
  const file = fileNode.files && fileNode.files[0];
  if (!file) return;
  const text = await file.text();
  exportNode.value = text;
  await importText(text);
  fileNode.value = "";
});

async function importText(text) {
  await run(async () => {
    const data = await api("/api/import", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    applyLibrary(data, `Разобрано звонков: ${data.imported}.`);
    exportNode.value = "";
  });
}

function applyLibrary(data, note) {
  library = data;
  renderCases();
  renderCoach();
  if (!session) renderDesk();
  if (note) noteNode.textContent = note;
}

async function startCall(caseId) {
  await run(async () => {
    const level = document.querySelector("#level").value;
    const focus = document.querySelector("#focus").value;
    const body = { case_id: caseId, level };
    if (focus) body.focus = focus;
    session = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    });
    renderAll();
    const field = document.querySelector("#say");
    if (field) field.focus();
  });
}

async function sendLine() {
  const field = document.querySelector("#say");
  if (!session || !field) return;
  const text = field.value;
  await run(async () => {
    session = await api(`/api/sessions/${session.id}/turn`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    renderAll();
    if (session.phase === "closed") await loadJournal();
  });
}

async function hangup() {
  if (!session) return;
  await run(async () => {
    session = await api(`/api/sessions/${session.id}/hangup`, { method: "POST", body: "{}" });
    renderAll();
    await loadJournal();
  });
}

async function repeatCall(row) {
  const select = document.querySelector("#level");
  if (select && row.level) select.value = row.level;
  const focus = document.querySelector("#focus");
  if (focus) focus.value = row.focus || "";
  await startCall(row.case_id);
}

async function removeCase(caseId) {
  await run(async () => {
    const data = await api(`/api/cases/${encodeURIComponent(caseId)}`, { method: "DELETE" });
    if (session && session.case_id === caseId) session = null;
    applyLibrary(data, "Звонок убран из библиотеки.");
    renderDesk();
  });
}

async function run(action) {
  if (busy) return;
  busy = true;
  noteNode.textContent = "";
  try {
    await action();
  } catch (error) {
    noteNode.textContent = error instanceof Error ? error.message : "Запрос не выполнен.";
  } finally {
    busy = false;
    const button = document.querySelector("#send");
    if (button) button.disabled = false;
  }
}

async function api(path, options) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Запрос не выполнен.");
  return data;
}

function renderAll() {
  renderCases();
  renderDesk();
  renderCoach();
}

function visibleCases() {
  const focus = document.querySelector("#focus").value;
  if (!focus) return library.cases;
  return library.cases.filter((item) => (item.kinds || []).some((entry) => entry.kind === focus));
}

function renderCases() {
  clear(casesNode);
  if (!library.cases.length) {
    casesNode.append(el("p", "empty", "Пока пусто. Загрузите выгрузку или откройте учебные звонки."));
    return;
  }
  const cases = visibleCases();
  if (!cases.length) {
    casesNode.append(el("p", "empty", "Нет карточек с этим возражением."));
    return;
  }
  for (const item of cases) {
    const card = el("article", session && session.case_id === item.id ? "case active" : "case");
    const who = item.client_name || "Клиент";
    const company = item.company ? ` · ${item.company}` : "";
    card.append(el("h3", "who", who + company));
    card.append(
      el(
        "p",
        "meta",
        `${item.product}. Исход в CRM: ${item.outcome_label}. Возражений: ${item.objection_count}.`,
      ),
    );
    const row = el("div", "row");
    const call = el("button", "", "Позвонить");
    call.type = "button";
    call.addEventListener("click", () => startCall(item.id));
    const drop = el("button", "quiet", "Убрать");
    drop.type = "button";
    drop.addEventListener("click", () => removeCase(item.id));
    row.append(call, drop);
    card.append(row);
    casesNode.append(card);
  }
}

function renderDesk() {
  window.clearInterval(timer);
  clear(deskNode);
  if (!session) {
    const blank = el("div", "empty-desk");
    blank.append(el("p", "", "Выберите карточку слева и нажмите «Позвонить». Клиент снимет трубку."));
    deskNode.append(blank);
    return;
  }
  const client = session.client;
  const sheet = el("div", session.phase === "closed" ? "sheet phase-closed" : "sheet");
  const top = el("div", "sheet-top");
  const title = el("div");
  const who = client.name || "Клиент";
  title.append(el("h2", "who", client.company ? `${who}, ${client.company}` : who));
  title.append(el("p", "meta", client.product));
  const side = el("div");
  const live = el("div", "live");
  live.append(el("i"));
  live.append(document.createTextNode(session.result_label));
  const clock = el("div", "timer", "00:00");
  clock.id = "timer";
  side.append(live, clock);
  top.append(title, side);
  const log = el("div", "log");
  for (const turn of session.transcript) {
    const bubble = el("p", `bubble ${turn.speaker}`);
    bubble.append(el("span", "speaker", turn.speaker === "client" ? "Клиент" : "Вы"));
    bubble.append(document.createTextNode(turn.text));
    log.append(bubble);
  }
  sheet.append(top, log);
  if (session.can_speak) {
    const composer = el("div", "composer");
    const field = document.createElement("textarea");
    field.id = "say";
    field.rows = 3;
    field.placeholder = "Что скажете клиенту";
    field.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendLine();
      }
    });
    const send = el("button", "", "Сказать");
    send.id = "send";
    send.type = "button";
    send.addEventListener("click", sendLine);
    const stop = el("button", "hang", "Положить трубку");
    stop.type = "button";
    stop.addEventListener("click", hangup);
    composer.append(field, send, stop);
    sheet.append(composer);
  } else {
    const again = el("button", "", "Позвонить по этой карточке ещё раз");
    again.type = "button";
    again.addEventListener("click", () => startCall(session.case_id));
    sheet.append(again);
  }
  deskNode.append(sheet);
  log.scrollTop = log.scrollHeight;
  paintTimer();
  if (!session.ended_ms) timer = window.setInterval(paintTimer, 1000);
}

function paintTimer() {
  const node = document.querySelector("#timer");
  if (!node || !session) return;
  const end = session.ended_ms || Date.now();
  const seconds = Math.max(0, Math.floor((end - session.started_ms) / 1000));
  const minutes = String(Math.floor(seconds / 60)).padStart(2, "0");
  const rest = String(seconds % 60).padStart(2, "0");
  node.textContent = `${minutes}:${rest}`;
}

async function loadJournal() {
  const node = document.querySelector("#journal");
  try {
    const data = await api("/api/journal");
    journal = Array.isArray(data.rows) ? data.rows : [];
    renderJournal();
  } catch (error) {
    clear(node);
    const message = error instanceof Error ? error.message : "Журнал не открылся.";
    node.append(el("p", "empty", message));
  }
}

function renderJournal() {
  const node = document.querySelector("#journal");
  clear(node);
  if (!journal.length) {
    node.append(el("p", "empty", "Пока пусто. Закрытый звонок появится здесь."));
    return;
  }
  for (const row of journal) {
    const card = el("article", "case");
    card.append(el("h3", "who", row.client_name || row.case_id));
    const level = LEVEL_LABEL[row.level] || row.level || "уровень не записан";
    const drill = row.focus_label ? ` Тренировка: ${row.focus_label}.` : "";
    const objections = row.objections ? ` · ${row.objections}` : "";
    const outcome = row.result_label || row.result;
    card.append(
      el("p", "meta", `${outcome}. ${level}.${drill} Закрыто ${row.handled} из ${row.spoken}${objections}.`),
    );
    const again = el("button", "quiet", "Ещё раз");
    again.type = "button";
    again.addEventListener("click", () => repeatCall(row));
    card.append(again);
    node.append(card);
  }
}

function renderCoach() {
  clear(coachNode);
  if (session) {
    coachNode.append(el("p", "", session.coach));
    const debrief = session.debrief;
    if (debrief) {
      coachNode.append(el("p", "meta", `${debrief.summary} Исход того звонка в CRM: ${debrief.source_outcome}.`));
      for (const study of debrief.studies) {
        const block = el("article", "study");
        const tag = el("span", `tag ${study.status}`, study.status_label);
        block.append(tag, el("h3", "who", study.label));
        block.append(el("p", "", `Клиент сказал: «${study.client_text}»`));
        appendQuotes(block, "После этой темы разговор в CRM шёл к договорённости или перезвону:", study.helpful);
        appendQuotes(block, "Так говорить не стоит — звонок в CRM закончился отказом:", study.unhelpful);
        coachNode.append(block);
      }
    }
    return;
  }
  if (!library.learned.length) {
    coachNode.append(el("p", "empty", "Когда появятся звонки, здесь будут возражения и реплики, с которыми они закончились."));
    return;
  }
  coachNode.append(el("p", "meta", "Это не подсказка к будущему звонку. Это то, что уже встречалось в выгрузке."));
  for (const item of library.learned) {
    const block = el("article", "quote");
    block.append(el("h3", "who", `${item.label} · ${item.product}`));
    block.append(el("p", "meta", `Встретилось раз: ${item.seen}.`));
    appendQuotes(block, "Клиенты говорили:", item.client_examples);
    appendQuotes(block, "Дальше была договорённость или перезвон:", item.helpful);
    appendQuotes(block, "Дальше был отказ:", item.unhelpful);
    coachNode.append(block);
  }
}

function appendQuotes(parent, title, lines) {
  if (!lines.length) return;
  parent.append(el("p", "meta", title));
  for (const line of lines) parent.append(el("p", "", `«${line}»`));
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

api("/api/library")
  .then((data) => {
    applyLibrary(data);
    return loadJournal();
  })
  .catch((error) => {
    noteNode.textContent = error instanceof Error ? error.message : "Библиотека не открылась.";
    renderAll();
  });
