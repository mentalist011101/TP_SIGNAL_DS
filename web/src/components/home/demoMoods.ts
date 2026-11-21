// Données de l'illustration animée de la page d'accueil. Ce ne sont PAS des résultats : la
// page le dit (« Illustration »). Elles montrent à quoi ressemble une analyse.

export interface DemoEmotion {
  label: string
  percent: number
}

// Une « humeur » de l'illustration : les six émotions, toujours dans le même ordre pour que
// les barres glissent sans changer de place, et l'allure du spectrogramme qui va avec.
export interface DemoMood {
  emotions: DemoEmotion[]
  // Écart entre deux harmoniques, en pixels : voix plus aiguë quand il est grand.
  harmonicSpacing: number
  // Amplitude du va-et-vient des bandes de fréquence, en pixels.
  formantSwing: number
  // Débit des syllabes : allumages et extinctions par seconde.
  syllableRate: number
}

// Durée d'une humeur avant de passer à la suivante.
export const MOOD_DURATION_MS = 2800

export const DEMO_MOODS: DemoMood[] = [
  {
    emotions: [
      { label: 'Colère', percent: 58 },
      { label: 'Neutre', percent: 24 },
      { label: 'Tristesse', percent: 9 },
      { label: 'Peur', percent: 5 },
      { label: 'Joie', percent: 3 },
      { label: 'Dégoût', percent: 1 },
    ],
    harmonicSpacing: 11,
    formantSwing: 38,
    syllableRate: 5.5,
  },
  {
    emotions: [
      { label: 'Colère', percent: 6 },
      { label: 'Neutre', percent: 21 },
      { label: 'Tristesse', percent: 3 },
      { label: 'Peur', percent: 4 },
      { label: 'Joie', percent: 64 },
      { label: 'Dégoût', percent: 2 },
    ],
    harmonicSpacing: 14,
    formantSwing: 46,
    syllableRate: 6.5,
  },
  {
    emotions: [
      { label: 'Colère', percent: 5 },
      { label: 'Neutre', percent: 71 },
      { label: 'Tristesse', percent: 12 },
      { label: 'Peur', percent: 3 },
      { label: 'Joie', percent: 8 },
      { label: 'Dégoût', percent: 1 },
    ],
    harmonicSpacing: 9,
    formantSwing: 18,
    syllableRate: 4,
  },
  {
    emotions: [
      { label: 'Colère', percent: 5 },
      { label: 'Neutre', percent: 27 },
      { label: 'Tristesse', percent: 52 },
      { label: 'Peur', percent: 11 },
      { label: 'Joie', percent: 3 },
      { label: 'Dégoût', percent: 2 },
    ],
    harmonicSpacing: 7,
    formantSwing: 12,
    syllableRate: 2.8,
  },
]

// Émotion la plus forte d'une humeur : celle qu'on affiche en grand.
export function dominantEmotion(mood: DemoMood): DemoEmotion {
  let best = mood.emotions[0]
  for (const emotion of mood.emotions) {
    if (emotion.percent > best.percent) {
      best = emotion
    }
  }
  return best
}
