let ws = null;
let audioContext = null;
let source = null;
let processor = null;
let stream = null;

const transcriptBox = document.getElementById("transcript");
const structuredBox = document.getElementById("structured");
const llmReportBox = document.getElementById("llmReport");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const transcriptCount = document.getElementById("transcriptCount");
const copyBtn = document.getElementById("copyBtn");
const pdfBtn = document.getElementById("pdfBtn");
const suggestionsBox = document.getElementById("suggestions");
const suggestionsCount = document.getElementById("suggestionsCount");
const likeBtn = document.getElementById("likeBtn");
const dislikeBtn = document.getElementById("dislikeBtn");

let activeSessionId = null;
let currentStructuredState = null;

let lineCount = 0;
let partialElement = null;

startBtn.onclick = startRecording;
stopBtn.onclick = stopRecording;
copyBtn.onclick = copyToClipboard;

if (likeBtn) likeBtn.onclick = () => sendFeedback("like");
if (dislikeBtn) dislikeBtn.onclick = () => sendFeedback("dislike");

function updateStatus(status, text) {
    statusDot.className = `status-dot ${status}`;
    statusText.textContent = text;
}

async function startRecording() {
    transcriptBox.innerHTML = "";
    structuredBox.innerHTML = "Waiting for structured data…";
    llmReportBox.textContent = "Waiting for clinical report…";
    transcriptCount.textContent = "0 lines";
    lineCount = 0;
    partialElement = null;
    activeSessionId = null;
    currentStructuredState = null;

    copyBtn.style.display = "none";
    if (pdfBtn) pdfBtn.style.display = "none";
    if (likeBtn) likeBtn.style.display = "none";
    if (dislikeBtn) dislikeBtn.style.display = "none";

    updateStatus("recording", "Recording…");
    startBtn.disabled = true;
    stopBtn.disabled = false;

    const wsScheme = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${wsScheme}://${location.host}/ws`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "partial") {
            showPartial(data.text);
            return;
        }

        if (data.type === "transcript") {
            clearPartial();
            appendTranscript(data.time, data.text, data.utterance_id);
            return;
        }

        if (data.type === "structured") {
            updateStatus("ready", "Report ready");
            activeSessionId = data.session_id;
            currentStructuredState = data.structured_state;

            if (likeBtn) likeBtn.style.display = "flex";
            if (dislikeBtn) dislikeBtn.style.display = "flex";
            copyBtn.style.display = "flex";

            renderStructured(currentStructuredState);

            llmReportBox.textContent =
                data.clinical_report || "No report generated.";

            if (data.pdf && pdfBtn) {
                pdfBtn.style.display = "flex";
                pdfBtn.onclick = () => window.open(data.pdf, "_blank");
            }

            if (data.system_suggestions) {
                renderSuggestions(data.system_suggestions);
            }
        }
    };

    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new AudioContext({ sampleRate: 16000 });
    source = audioContext.createMediaStreamSource(stream);
    processor = audioContext.createScriptProcessor(4096, 1, 1);

    source.connect(processor);
    processor.connect(audioContext.destination);

    processor.onaudioprocess = (e) => {
        if (ws?.readyState === WebSocket.OPEN) {
            ws.send(floatTo16BitPCM(e.inputBuffer.getChannelData(0)));
        }
    };
}

function stopRecording() {
    updateStatus("processing", "Finalizing…");
    stopBtn.disabled = true;
    ws?.send(JSON.stringify({ type: "stop" }));
}

function showPartial(text) {
    if (!partialElement) {
        partialElement = document.createElement("div");
        partialElement.className = "transcript-line partial";
        transcriptBox.appendChild(partialElement);
    }
    partialElement.innerHTML = `<i>${text}</i>`;
}

function clearPartial() {
    partialElement?.remove();
    partialElement = null;
}

/* ---------------- TRANSCRIPT EDITING ---------------- */

function appendTranscript(time, text, utteranceId) {
    const line = document.createElement("div");
    line.className = "transcript-line";
    line.dataset.utteranceId = utteranceId;

    line.innerHTML = `
        <span class="timestamp">[${time}]</span>
        <span class="content">${text}</span>
    `;

    line.onclick = () => enableTranscriptEdit(line);

    transcriptBox.appendChild(line);
    transcriptBox.scrollTop = transcriptBox.scrollHeight;

    transcriptCount.textContent = `${++lineCount} lines`;
}

function enableTranscriptEdit(line) {
    if (!activeSessionId) return;

    const content = line.querySelector(".content");
    const oldText = content.textContent;
    const utteranceId = line.dataset.utteranceId;

    const input = document.createElement("input");
    input.value = oldText;
    content.replaceWith(input);
    input.focus();

    input.onkeydown = async (e) => {
        if (e.key === "Enter") {
            const newText = input.value.trim();
            if (newText !== oldText) {
                await submitTranscriptEdit({
                    sessionId: activeSessionId,
                    utteranceId,
                    field: "text",
                    oldValue: oldText,
                    newValue: newText,
                });
            }
            content.textContent = newText || oldText;
            input.replaceWith(content);
        }
        if (e.key === "Escape") input.replaceWith(content);
    };
}

/* ---------------- STRUCTURED EDITING ---------------- */

function renderStructured(state) {
    structuredBox.innerHTML = "";
    renderSection("Diagnosis", "diagnosis");
    renderSection("Tests Advised", "tests");
    renderSection("Medications", "medications");
    renderSection("Advice", "advice");
}

function renderSection(title, key) {
    const section = document.createElement("div");
    section.className = "structured-section";

    const header = document.createElement("div");
    header.className = "structured-header";
    header.textContent = title;

    const list = document.createElement("div");
    list.className = "structured-list";


    (currentStructuredState[key] || []).forEach(item => {
        const row = document.createElement("div");
        row.className = "structured-item";

        const label = document.createElement("span");
        label.textContent = typeof item === "string" ? item : item.name;

        const del = document.createElement("button");
        del.className = "structured-remove";
        del.innerHTML = "×";

        del.onclick = async () => {
            await submitStructuredEdit({
                sessionId: activeSessionId,
                section: key,
                action: "remove",
                value: item,
            });
            currentStructuredState[key] =
                currentStructuredState[key].filter(v => v !== item);
            renderStructured(currentStructuredState);
        };

        row.appendChild(label);
        row.appendChild(del);
        list.appendChild(row);
    });

    const addBtn = document.createElement("button");
    addBtn.className = "structured-add";
    addBtn.textContent = `+ Add ${title}`;

    addBtn.onclick = async () => {
        const value = prompt(`Enter ${title}`);
        if (!value) return;

        const payload = key === "medications" ? { name: value } : value;

        await submitStructuredEdit({
            sessionId: activeSessionId,
            section: key,
            action: "add",
            value: payload,
        });

        currentStructuredState[key].push(payload);
        renderStructured(currentStructuredState);
    };
    section.appendChild(header);
    section.appendChild(ul);
    section.appendChild(addBtn);
    structuredBox.appendChild(section);
}

/* ---------------- API ---------------- */

async function submitTranscriptEdit(payload) {
    await fetch(`/sessions/${payload.sessionId}/transcript-edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, edit_id: crypto.randomUUID() }),
    });
}

async function submitStructuredEdit(payload) {
    await fetch(`/sessions/${payload.sessionId}/structured-edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, edit_id: crypto.randomUUID() }),
    });
}

/* ---------------- MISC ---------------- */

function floatTo16BitPCM(input) {
    const buf = new ArrayBuffer(input.length * 2);
    const view = new DataView(buf);
    input.forEach((s, i) => view.setInt16(i * 2, s * 0x7fff, true));
    return buf;
}

function cleanupAudio() {
    processor?.disconnect();
    source?.disconnect();
    stream?.getTracks().forEach(t => t.stop());
}

function copyToClipboard() {
    navigator.clipboard.writeText(llmReportBox.textContent);
}
