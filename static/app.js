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

let lineCount = 0;
let partialElement = null;

startBtn.onclick = startRecording;
stopBtn.onclick = stopRecording;
copyBtn.onclick = copyToClipboard;

function updateStatus(status, text) {
    statusDot.className = `status-dot ${status}`;
    statusText.textContent = text;
}

async function startRecording() {
    // Reset UI
    transcriptBox.innerHTML = "";
    structuredBox.textContent = "Waiting for structured data...";
    llmReportBox.textContent = "Waiting for clinical report...";
    transcriptCount.textContent = "0 lines";
    lineCount = 0;
    partialElement = null;

    copyBtn.style.display = "none";
    if (pdfBtn) pdfBtn.style.display = "none";

    updateStatus("recording", "Recording…");
    startBtn.disabled = true;
    stopBtn.disabled = false;

    const wsScheme = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${wsScheme}://${location.host}/ws`);

    ws.onerror = (e) => {
        console.error("WebSocket error", e);
        updateStatus("", "Connection error");
        startBtn.disabled = false;
        stopBtn.disabled = true;
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "partial") {
            showPartial(data.text);
            return;
        }

        if (data.type === "transcript") {
            clearPartial();
            appendTranscript(data.time, data.text);
            return;
        }

        if (data.type === "structured") {
            updateStatus("ready", "Report ready");

            // Structured JSON
            structuredBox.textContent =
                data.structured_state
                    ? JSON.stringify(data.structured_state, null, 2)
                    : "No structured data received.";

            llmReportBox.textContent =
                data.clinical_report || "No report generated.";

            copyBtn.style.display = "flex";

            // PDF button
            if (data.pdf && pdfBtn) {
                pdfBtn.style.display = "flex";
                pdfBtn.onclick = () => window.open(data.pdf, "_blank");
            }

            return;
        }
    };

    // Audio capture
    try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        audioContext = new AudioContext({ sampleRate: 16000 });
        await audioContext.resume();

        source = audioContext.createMediaStreamSource(stream);
        processor = audioContext.createScriptProcessor(4096, 1, 1);

        source.connect(processor);
        processor.connect(audioContext.destination);

        processor.onaudioprocess = (event) => {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            const input = event.inputBuffer.getChannelData(0);
            ws.send(floatTo16BitPCM(input));
        };
    } catch (err) {
        console.error("Microphone error", err);
        updateStatus("", "Microphone access denied");
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

function stopRecording() {
    updateStatus("processing", "Finalizing report…");
    stopBtn.disabled = true;

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "stop" }));
    }

    setTimeout(() => {
        cleanupAudio();
        startBtn.disabled = false;
    }, 300);
}

function showPartial(text) {
    if (!partialElement) {
        partialElement = document.createElement("div");
        partialElement.className = "transcript-line partial";
        transcriptBox.appendChild(partialElement);
    }
    partialElement.innerHTML =
        `<span style="color:#888;font-style:italic;">${text}</span>`;
    transcriptBox.scrollTop = transcriptBox.scrollHeight;
}

function clearPartial() {
    if (partialElement) {
        partialElement.remove();
        partialElement = null;
    }
}

function appendTranscript(time, text) {
    const line = document.createElement("div");
    line.className = "transcript-line";
    line.textContent = `[${time}] ${text}`;
    transcriptBox.appendChild(line);
    transcriptBox.scrollTop = transcriptBox.scrollHeight;

    lineCount++;
    transcriptCount.textContent =
        `${lineCount} line${lineCount !== 1 ? "s" : ""}`;
}

function floatTo16BitPCM(float32Array) {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    let offset = 0;

    for (let i = 0; i < float32Array.length; i++, offset += 2) {
        let sample = Math.max(-1, Math.min(1, float32Array[i]));
        view.setInt16(offset, sample * 0x7fff, true);
    }
    return buffer;
}

function cleanupAudio() {
    if (processor) {
        processor.disconnect();
        processor = null;
    }
    if (source) {
        source.disconnect();
        source = null;
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    if (stream) {
        stream.getTracks().forEach(t => t.stop());
        stream = null;
    }
}

function copyToClipboard() {
    const text = llmReportBox.textContent;
    if (!text) return;

    navigator.clipboard.writeText(text).then(() => {
        const icon = copyBtn.querySelector(".material-icons");
        icon.textContent = "check";
        setTimeout(() => {
            icon.textContent = "content_copy";
        }, 1500);
    });
}