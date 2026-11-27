// Mise en forme de la page Locuteurs (EF-11) : durées et dates au format français.

// Parole demandée pour enregistrer une voix, extraits réunis : configs/inference.yaml
// (speaker.min_enrollment_speech_s). Le serveur refuse en dessous, avec un message.
export const MIN_SPEECH_SECONDS = 10

// Version du texte de consentement affiché (VoiceConsent) : configs/inference.yaml
// (speaker.consent_version). Changer le texte oblige à changer la version des deux côtés.
export const SPEAKER_CONSENT_VERSION = 'locuteurs-v1'

// « 12,3 s » : une durée en secondes, une décimale.
export function formatSpeech(seconds: number): string {
  const formatted = seconds.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${formatted} s`
}

// « 27 nov. 2026 » : la date d'enregistrement d'une voix.
export function formatDay(isoDate: string): string {
  const date = new Date(isoDate)
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
}

// « 1 extrait », « 2 extraits » : un nombre et son nom, accordé.
export function countLabel(count: number, singular: string, plural: string): string {
  if (count === 1) {
    return `1 ${singular}`
  }
  return `${count} ${plural}`
}
