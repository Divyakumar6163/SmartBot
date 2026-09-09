document.addEventListener("DOMContentLoaded", () => {

    // ==============================
    // CONFIG
    // ==============================
    const API_BASE = "http://35.163.181.133:8000"; // AWS EC2 backend

    let recorder = null;
    let audioChunks = [];
    let state = "idle";

    const mic = document.getElementById("mic");
    const ear = document.getElementById("ear");
    const eq = document.getElementById("eq");
    const status = document.getElementById("status");
    const result = document.getElementById("result");

    function show(el) { el.classList.remove("hidden"); }
    function hide(el) { el.classList.add("hidden"); }

    // ==============================
    // RECORDING
    // ==============================
    async function startRecording() {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                noiseSuppression: true,
                echoCancellation: true,
                autoGainControl: true
            }
        });

        recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
        audioChunks = [];

        recorder.ondataavailable = e => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        recorder.onstop = sendAudio;
        recorder.start();

        hide(mic);
        show(ear);
        status.innerText = "Listening... tap again to stop.";
        state = "listening";
    }

    function stopRecording() {
        if (recorder && recorder.state === "recording") {
            recorder.stop();
            hide(ear);
            show(eq);
            status.innerText = "Processing...";
            state = "processing";
        }
    }

    // ==============================
    // SEND AUDIO TO BACKEND
    // ==============================
    async function sendAudio() {
        const blob = new Blob(audioChunks, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("file", blob, "speech.webm");

        try {
            const res = await fetch(`${API_BASE}/transcribe`, {
                method: "POST",
                body: formData
            });

            const data = await res.json();
            result.innerText = data.text;

            // play returned audio
            const audioBytes = Uint8Array.from(
                atob(data.audio),
                c => c.charCodeAt(0)
            );

            const audioBlob = new Blob([audioBytes], { type: "audio/mp3" });
            const audio = new Audio(URL.createObjectURL(audioBlob));

            status.innerText = "Speaking...";
            await audio.play();

            audio.onended = resetUI;

        } catch (err) {
            console.error(err);
            resetUI();
        }
    }

    // ==============================
    // UI RESET
    // ==============================
    function resetUI() {
        hide(eq);
        hide(ear);
        show(mic);
        status.innerText = "Tap to speak";
        state = "idle";
    }

    // ==============================
    // EVENTS
    // ==============================
    mic.onclick = () => state === "idle" && startRecording();
    ear.onclick = () => state === "listening" && stopRecording();

});
