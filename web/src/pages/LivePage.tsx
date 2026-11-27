import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { SavedMessage, WindowMessage } from '../api/stream.ts'
import LiveMetrics from '../components/live/LiveMetrics.tsx'
import LiveResults from '../components/live/LiveResults.tsx'
import RecordingConsent from '../components/live/RecordingConsent.tsx'
import { useLiveStream, type LiveStatus } from '../components/live/useLiveStream.ts'
import DemoNotice from '../components/result/DemoNotice.tsx'

// Page Direct (C23, EF-14) : le micro est analysé en continu par le serveur, par fenêtres de
// 2 s toutes les 0,5 s (D8), avec les modèles du profil Temps réel. La page affiche les
// résultats, le temps de calcul, le RTF et la latence perçue ; elle peut enregistrer la
// session dans l'Historique, avec consentement (ENF-10).

const PRIMARY_BUTTON_CLASSES =
  'rounded-btn bg-accent px-5 py-2.5 font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-50'
const LINK_CLASSES = 'font-semibold text-accent-ink underline underline-offset-4'
const DEMO_MODEL_ID = 'demo'

// Vrai tant que la session occupe le micro ou la connexion.
function isRunning(status: LiveStatus): boolean {
  return status === 'connecting' || status === 'live' || status === 'stopping'
}

// Vrai si la fenêtre vient du faux prédicteur (mode demo) : on le dit avant les chiffres.
function isDemoWindow(latest: WindowMessage | null): boolean {
  if (latest === null) {
    return false
  }
  const emotion = latest.results.emotion
  const soundEvent = latest.results.sound_event
  return emotion?.model_id === DEMO_MODEL_ID || soundEvent?.model_id === DEMO_MODEL_ID
}

// « En direct » avec un point vert qui pulse (arrêté si le système demande moins d'animations).
function LiveBadge({ status }: { status: LiveStatus }) {
  let text = 'Connexion…'
  if (status === 'live') {
    text = 'En direct'
  } else if (status === 'stopping') {
    text = 'Arrêt…'
  }
  return (
    <span className="inline-flex items-center gap-2 text-sm font-semibold">
      <span className="relative flex h-2.5 w-2.5" aria-hidden="true">
        <span className="absolute inset-0 rounded-full bg-brand motion-safe:animate-ping" />
        <span className="relative h-2.5 w-2.5 rounded-full bg-brand" />
      </span>
      {text}
    </span>
  )
}

// Lien vers l'analyse créée à partir de la session enregistrée.
function SavedNotice({ saved }: { saved: SavedMessage }) {
  return (
    <p className="text-sm">
      Session enregistrée dans l’Historique.{' '}
      <Link to={`/analyses/${saved.analysis_id}`} className={LINK_CLASSES}>
        Voir son analyse
      </Link>
      {saved.truncated && ' (coupée à 5 minutes).'}
    </p>
  )
}

export default function LivePage() {
  const { state, start, stop } = useLiveStream()
  const [record, setRecord] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const running = isRunning(state.status)
  // Pour enregistrer, le consentement doit être coché avant de démarrer (ENF-10).
  const canStart = !running && (!record || accepted)
  const hopS = state.ready?.hop_s ?? 0.5

  function handleRecordChange(nextRecord: boolean) {
    setRecord(nextRecord)
    setAccepted(false)
  }

  return (
    <section className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-5xl leading-tight">Analyse en direct</h1>
        <p className="max-w-3xl text-ink-soft">
          Parlez dans le micro : toutes les 0,5 s, EchoLens analyse les 2 dernières secondes
          (émotion et événement sonore) avec les modèles du profil Temps réel, et affiche le temps
          de calcul et la latence.
        </p>
      </div>
      <div className="space-y-5 rounded-card border border-rule bg-card p-5">
        <RecordingConsent
          record={record}
          accepted={accepted}
          disabled={running}
          onRecordChange={handleRecordChange}
          onAcceptedChange={setAccepted}
        />
        {!record && (
          <p className="text-sm text-ink-soft">
            Sans enregistrement, rien n’est conservé : le serveur ne garde que les 2 dernières
            secondes, le temps de les analyser.
          </p>
        )}
        <div className="flex flex-wrap items-center gap-4">
          {!running && (
            <button
              type="button"
              className={PRIMARY_BUTTON_CLASSES}
              disabled={!canStart}
              onClick={() => start(record)}
            >
              Démarrer
            </button>
          )}
          {running && (
            <button
              type="button"
              className={PRIMARY_BUTTON_CLASSES}
              disabled={state.status !== 'live'}
              onClick={stop}
            >
              Arrêter
            </button>
          )}
          {running && <LiveBadge status={state.status} />}
        </div>
        {state.error !== null && <p className="text-sm text-danger">{state.error}</p>}
        {state.saved !== null && <SavedNotice saved={state.saved} />}
      </div>
      {isDemoWindow(state.lastWindow) && <DemoNotice />}
      <LiveResults latest={state.lastWindow} />
      <LiveMetrics
        latest={state.lastWindow}
        hopS={hopS}
        latencyMs={state.latencyMs}
        latencyP50Ms={state.latencyP50Ms}
        latencyP95Ms={state.latencyP95Ms}
      />
    </section>
  )
}
