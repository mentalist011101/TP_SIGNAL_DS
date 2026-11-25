import Reveal from './Reveal.tsx'

// Limites connues, d'après les fiches des modèles (docs/models/) et les essais sur des audios
// réels (PR #28).
const LIMITS: string[] = [
  'La détection de parole (VAD) prend parfois un bruit régulier pour de la voix : sur l’extrait de pluie, une émotion est estimée alors qu’il n’y a personne.',
  'ESC-50 n’a pas de classe « parole » : une voix est rangée dans le son le plus proche (éternuement, toux). Et un son hors des 50 classes reçoit quand même l’une d’elles.',
  'Un seul événement par fenêtre de 5 s : deux sons simultanés ne sont pas séparés.',
  'Émotions : F1 de 0,805 sur les voix féminines contre 0,702 sur les voix masculines ; voix d’acteurs, en anglais. Le français et les accents africains restent à mesurer (CaFE, African Accented French).',
  'La robustesse au bruit et aux micros des téléphones n’est pas encore mesurée.',
  'Transcription : 14 % de mots faux (WER) sur le test d’OpenSLR 57, mais 35 % avec l’accent camerounais du corpus de Yaoundé (whisper-small, profil Qualité).',
  'Les locuteurs ne sont pas encore branchés.',
  'Plusieurs jeux d’entraînement sont sous licence non commerciale (ESC-50, RAVDESS) : usage académique uniquement.',
]

// Section « limites » : ce que les modèles ne savent pas encore faire, dit simplement.
export default function Limits() {
  return (
    <section className="mx-auto max-w-6xl space-y-10 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Limites</p>
        <h2 className="font-display text-5xl leading-tight">
          Ce qu’EchoLens <em className="text-ink-soft">ne sait pas encore</em> faire.
        </h2>
      </Reveal>
      <Reveal>
        <ul className="divide-y divide-rule rounded-card border border-rule bg-card">
          {LIMITS.map((limit) => (
            <li key={limit} className="flex gap-4 px-6 py-4 leading-relaxed">
              <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ink-faint" />
              <span>{limit}</span>
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  )
}
