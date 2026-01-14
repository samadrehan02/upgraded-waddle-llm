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

let lineCount = 0;
let partialElement = null;  // Track the partial result div

startBtn.onclick = startRecording;
stopBtn.onclick = stopRecording;
copyBtn.onclick = copyToClipboard;

function updateStatus(status, text) {
    statusDot.className = `status-dot ${status}`;
    statusText.textContent = text;
}

function clearEmptyStates() {
    const emptyStates = document.querySelectorAll('.empty-state');
    emptyStates.forEach(el => el.remove());
}

async function startRecording() {
    // Clear previous session
    transcriptBox.innerHTML = "";
    structuredBox.textContent = "";
    llmReportBox.textContent = "";
    lineCount = 0;
    partialElement = null;
    transcriptCount.textContent = "0 lines";
    copyBtn.style.display = "none";
    clearEmptyStates();

    updateStatus("recording", "Recording...");
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
            // Show partial result (live, uncommitted text)
            showPartial(data.text);
            return;
        }

        if (data.type === "transcript") {
            // Remove partial and append final transcript
            clearPartial();
            appendTranscript(data.time, data.text);
            return;
        }
        if (data.type === "structured") {
            updateStatus("ready", "Report generated");

            // Show structured JSON (optional)
            structuredBox.textContent = JSON.stringify(data.data, null, 2);

            // Show clinical report directly from WebSocket payload
            const report =
                data.data?.data?.clinical_report ??
                data.data?.clinical_report ??
                "❌ No report generated.";

            llmReportBox.textContent = report;
            copyBtn.style.display = "flex";
            return;
        }

    };

    // Start audio capture with larger buffer for efficiency
    try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new AudioContext({sampleRate: 16000});
        await audioContext.resume();
        source = audioContext.createMediaStreamSource(stream);

        // Increased buffer size from 1024 to 4096 for better efficiency
        processor = audioContext.createScriptProcessor(4096, 1, 1);
        source.connect(processor);
        processor.connect(audioContext.destination);

        processor.onaudioprocess = (event) => {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            const input = event.inputBuffer.getChannelData(0);
            const pcm = floatTo16BitPCM(input);
            ws.send(pcm);
        };
    } catch (err) {
        console.error("Microphone access denied", err);
        updateStatus("", "Microphone error");
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

function stopRecording() {
    updateStatus("processing", "Processing consultation...");
    stopBtn.disabled = true;

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send("stop");
    }

    setTimeout(() => {
        cleanupAudio();
        startBtn.disabled = false;
    }, 300);
}

function showPartial(text) {
    // Create or update the partial result element
    if (!partialElement) {
        partialElement = document.createElement("div");
        partialElement.className = "transcript-line partial";
        transcriptBox.appendChild(partialElement);
    }

    // Update partial text with styling to indicate it's temporary
    partialElement.innerHTML = `<span style="color: #888; font-style: italic;">${text}</span>`;
    transcriptBox.scrollTop = transcriptBox.scrollHeight;
}

function clearPartial() {
    // Remove partial element when final result arrives
    if (partialElement) {
        partialElement.remove();
        partialElement = null;
    }
}

function appendTranscript(time, text) {
    const line = document.createElement("div");
    line.className = "transcript-line";
    line.innerHTML = `[${time}] ${text}`;
    transcriptBox.appendChild(line);
    transcriptBox.scrollTop = transcriptBox.scrollHeight;

    lineCount++;
    transcriptCount.textContent = `${lineCount} line${lineCount !== 1 ? 's' : ''}`;
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
    navigator.clipboard.writeText(text).then(() => {
        const icon = copyBtn.querySelector('.material-icons');
        icon.textContent = 'check';
        setTimeout(() => {
            icon.textContent = 'content_copy';
        }, 2000);
    });
}