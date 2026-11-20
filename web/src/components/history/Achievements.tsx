import type { CSSProperties } from 'react'
import type { HistoryStats } from './historyStats.ts'

const SECONDS_PER_MINUTE = 60

interface Achievement {
  title: string
  description: string
  current: number
  target: number
}

// Les badges et leur objectif. Ils se débloquent avec les vraies analyses de l'historique,
// jamais avec des chiffres inventés.
function buildAchievements(stats: HistoryStats): Achievement[] {
  const analysedMinutes = Math.floor(stats.analysedSeconds / SECONDS_PER_MINUTE)
  return [
    {
      title: 'Premier pas',
      description: 'Terminer une première analyse',
      current: stats.doneCount,
      target: 1,
    },
    {
      title: 'Habitué',
      description: 'Terminer 10 analyses',
      current: stats.doneCount,
      target: 10,
    },
    {
      title: 'Explorateur',
      description: 'Essayer les 4 tâches',
      current: stats.tasksTried,
      target: 4,
    },
    {
      title: 'Oreille fine',
      description: 'Analyser 5 minutes d’audio',
      current: analysedMinutes,
      target: 5,
    },
    {
      title: 'Au micro',
      description: 'Analyser un enregistrement',
      current: stats.recordingCount,
      target: 1,
    },
    {
      title: 'Régulier',
      description: 'Analyser 3 jours d’affilée',
      current: stats.streakDays,
      target: 3,
    },
  ]
}

function isUnlocked(achievement: Achievement): boolean {
  return achievement.current >= achievement.target
}

// Avancement de 0 à 100 %, plafonné à l'objectif.
function progressStyle(achievement: Achievement): CSSProperties {
  const reached = Math.min(achievement.current, achievement.target)
  const percent = (reached / achievement.target) * 100
  return { width: `${percent}%` }
}

// Médaille : pleine si le badge est débloqué, en simple contour sinon.
function Medal({ unlocked }: { unlocked: boolean }) {
  let classes = 'border border-rule-strong text-ink-faint'
  if (unlocked) {
    classes = 'bg-ink text-paper'
  }
  return (
    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${classes}`}>
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
        <path d="M12 2l2.9 6.2 6.6.6-5 4.5 1.5 6.6L12 16.6 6 19.9l1.5-6.6-5-4.5 6.6-.6z" />
      </svg>
    </span>
  )
}

// Un badge : médaille, titre, objectif, puis l'avancement s'il n'est pas encore débloqué.
function AchievementCard({ achievement }: { achievement: Achievement }) {
  const unlocked = isUnlocked(achievement)
  return (
    <li className="flex gap-3 bg-card p-4">
      <Medal unlocked={unlocked} />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-semibold">{achievement.title}</p>
        <p className="text-xs text-ink-soft">{achievement.description}</p>
        {unlocked && <p className="label-mono text-ink">Débloqué</p>}
        {!unlocked && (
          <div className="flex items-center gap-2">
            <span className="h-1.5 flex-1 rounded-btn bg-paper-alt" aria-hidden="true">
              <span
                className="block h-full rounded-btn bg-ink-soft"
                style={progressStyle(achievement)}
              />
            </span>
            <span className="font-mono text-xs text-ink-soft">
              {achievement.current} / {achievement.target}
            </span>
          </div>
        )}
      </div>
    </li>
  )
}

// Badges de l'historique : un peu de jeu pour donner envie d'essayer toutes les tâches.
export default function Achievements({ stats }: { stats: HistoryStats }) {
  const achievements = buildAchievements(stats)
  let unlockedCount = 0
  for (const achievement of achievements) {
    if (isUnlocked(achievement)) {
      unlockedCount += 1
    }
  }
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-lg font-bold">Badges</h2>
        <p className="font-mono text-sm text-ink-soft">
          {unlockedCount} / {achievements.length} débloqués
        </p>
      </div>
      {/* Même grille à filets fins que les chiffres clés. */}
      <ul className="grid gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-3">
        {achievements.map((achievement) => (
          <AchievementCard key={achievement.title} achievement={achievement} />
        ))}
      </ul>
    </section>
  )
}
