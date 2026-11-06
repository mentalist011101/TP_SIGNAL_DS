import { useRef, useState } from "react";

export default function AnalyzePage() {
  const [audioUrl, setAudioUrl] = useState("");
  const [audioName, setAudioName] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [profile, setProfile] = useState("qualite");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState("");

  const [emotion, setEmotion] = useState(true);
  const [event, setEvent] = useState(true);
  const [transc, setTransc] = useState(false);
  const [speakers, setSpeakers] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const waveRef = useRef<HTMLCanvasElement>(null);
  const specRef = useRef<HTMLCanvasElement>(null);
  const onFile = (file: File | undefined) => { if (!file) return; const url = URL.createObjectURL(file); setAudioUrl(url); setAudioName(file.name); setMessage("Fichier charge : " + file.name); drawWave(url); };
const drawWave = async (url: string) => { try { const ctx = new AudioContext(); const res = await fetch(url); const buf = await res.arrayBuffer(); const audioBuf = await ctx.decodeAudioData(buf); const data = audioBuf.getChannelData(0);
  const canvas = waveRef.current;
  if (canvas) {
    const c = canvas.getContext("2d")!;
    c.fillStyle = "#0f172a";
    c.fillRect(0, 0, canvas.width, canvas.height);
    c.strokeStyle = "#22c55e";
    c.beginPath();
    for (let x = 0; x < canvas.width; x++) {
      const v = data[Math.floor((x / canvas.width) * data.length)] || 0;
      const y = canvas.height / 2 + v * 60;
      if (x === 0) c.moveTo(x, y);
      else c.lineTo(x, y);
    }
    c.stroke();
  }

  const canvas2 = specRef.current;
  if (canvas2) {
    const c2 = canvas2.getContext("2d")!;
    for (let x = 0; x < canvas2.width; x++) {
      for (let y = 0; y < canvas2.height; y++) {
        const v = Math.abs(data[Math.floor((x / canvas2.width) * data.length)] || 0);
        const n = Math.floor(v * 200 + 20);
        c2.fillStyle = "rgb(" + n + "," + Math.floor(n * 0.6) + ",80)";
        c2.fillRect(x, y, 1, 1);
      }
    }
  }
  ctx.close();
} catch {
  setMessage("Impossible de dessiner");
}
};
const toggleRecord = async () => {
    if (isRecording) {
      mediaRef.current?.stop();
      setIsRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        setAudioName("enregistrement.webm");
        drawWave(url);
        setMessage("Enregistrement termine");
      };
      rec.start();
      mediaRef.current = rec;
      setIsRecording(true);
      setMessage("Enregistrement en cours...");
    } catch {
      setMessage("Micro non autorise");
    }
  };

  const onAnalyze = () => {
    if (!audioUrl) {
      setMessage("D abord importe un fichier");
      return;
    }
    setMessage("Analyse lancee - Profil : " + profile);
    setResult("Demo : Emotion = Neutre (62%), Evenement = Voix (71%)");
  };
  return ( <div style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}> <h1>Analyser un audio</h1> <p>Importe ou enregistre, puis analyse.</p>
  <div style={{ display: "flex", gap: 12 }}>
    <input
      ref={fileRef}
      type="file"
      accept=".wav,.mp3,.flac,.ogg,.webm"
      hidden
      onChange={(e) => onFile(e.target.files?.[0])}
    />
    <button onClick={() => fileRef.current?.click()}>
      Importer un fichier
    </button>
    <button onClick={toggleRecord}>
      {isRecording ? "Arreter" : "Enregistrer au micro"}
    </button>
  </div>

  {audioName && <p>Fichier : {audioName}</p>}
  {message && <p>{message}</p>}

  <h3>Que veux-tu analyser ?</h3>
  <label style={{ display: "block" }}>
    <input
      type="checkbox"
      checked={emotion}
      onChange={() => setEmotion(!emotion)}
    />
    Emotion
  </label>
  <label style={{ display: "block" }}>
    <input
      type="checkbox"
      checked={event}
      onChange={() => setEvent(!event)}
    />
    Evenement sonore
  </label>
  <label style={{ display: "block" }}>
    <input
      type="checkbox"
      checked={transc}
      onChange={() => setTransc(!transc)}
    />
    Transcription
  </label>
  <label style={{ display: "block" }}>
    <input
      type="checkbox"
      checked={speakers}
      onChange={() => setSpeakers(!speakers)}
    />
    Locuteurs
  </label>

  <label style={{ display: "block", marginTop: 12 }}>
    Profil :
    <select
      value={profile}
      onChange={(e) => setProfile(e.target.value)}
    >
      <option value="qualite">Qualite</option>
      <option value="temps-reel">Temps reel</option>
    </select>
  </label>

  <button
    onClick={onAnalyze}
    style={{ marginTop: 16, padding: "10px 20px" }}
  >
    ANALYSER
  </button>

  {audioUrl && (
    <div style={{ marginTop: 20 }}>
      <audio controls src={audioUrl} style={{ width: "100%" }} />
      <h3>Forme d onde</h3>
      <canvas
        ref={waveRef}
        width={850}
        height={140}
        style={{ width: "100%" }}
      />
      <h3>Spectrogramme</h3>
      <canvas
        ref={specRef}
        width={850}
        height={160}
        style={{ width: "100%" }}
      />
    </div>
  )}

  {result && <p>{result}</p>}
</div>
); }