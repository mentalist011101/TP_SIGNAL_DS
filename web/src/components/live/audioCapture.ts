import { STREAM_SAMPLE_RATE } from '../../api/stream.ts'
// no-inline : un vrai fichier .js, pas une URL data: intégrée au bundle, pour addModule.
import workletUrl from './pcm-capture.worklet.js?url&no-inline'

// Capture du micro pour la page Direct (C23, D8) : le navigateur convertit le son en 16 kHz
// (AudioContext à 16 kHz), puis le processeur AudioWorklet envoie des morceaux de 100 ms en
// PCM Int16. Aucun calcul sur le signal ici : seulement le format attendu par le serveur.

export interface AudioCapture {
  stop: () => void
}

// Erreur de capture, avec un message en français affichable tel quel.
export class CaptureError extends Error {}

// Micro sans les traitements du navigateur (annulation d'écho, réduction de bruit, gain
// automatique) : le serveur reçoit le son tel qu'il est, comme un fichier importé.
const MICROPHONE_CONSTRAINTS: MediaStreamConstraints = {
  audio: {
    channelCount: 1,
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: false,
  },
}

async function openMicrophone(): Promise<MediaStream> {
  try {
    return await navigator.mediaDevices.getUserMedia(MICROPHONE_CONSTRAINTS)
  } catch {
    throw new CaptureError(
      'Micro inaccessible : autorisez le micro dans le navigateur, puis réessayez.',
    )
  }
}

// Relie le micro au processeur dans un contexte à 16 kHz. Firefox refuse de relier un micro à
// un contexte d'une autre fréquence : on le dit plutôt que d'échouer sans message.
function connectSource(context: AudioContext, stream: MediaStream): MediaStreamAudioSourceNode {
  try {
    return context.createMediaStreamSource(stream)
  } catch {
    throw new CaptureError(
      'Ce navigateur ne sait pas convertir le micro en 16 kHz : utilisez Chrome ou Edge.',
    )
  }
}

// Coupe chaque piste du micro : le voyant d'enregistrement du navigateur s'éteint.
function stopTracks(stream: MediaStream): void {
  for (const track of stream.getTracks()) {
    track.stop()
  }
}

// Démarre la capture ; onChunk reçoit chaque morceau de 100 ms (PCM Int16, 16 kHz).
export async function startCapture(onChunk: (chunk: ArrayBuffer) => void): Promise<AudioCapture> {
  // Étape 1 : le micro, puis un contexte audio à 16 kHz (D8).
  const stream = await openMicrophone()
  const context = new AudioContext({ sampleRate: STREAM_SAMPLE_RATE })
  await context.audioWorklet.addModule(workletUrl)
  // Étape 2 : micro → processeur. Le processeur est relié à la sortie pour que le navigateur
  // le fasse tourner ; il n'écrit rien, donc on n'entend rien.
  const source = connectSource(context, stream)
  const processor = new AudioWorkletNode(context, 'pcm-capture')
  processor.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
    onChunk(event.data)
  }
  source.connect(processor)
  processor.connect(context.destination)
  // Étape 3 : l'arrêt coupe tout, micro compris.
  function stop(): void {
    source.disconnect()
    processor.disconnect()
    stopTracks(stream)
    void context.close()
  }
  return { stop }
}
