import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import type { ClassProbability } from '../../api/client.ts'
import { readCssColor } from '../../theme.ts'
import { formatPercent } from './format.ts'

// Hauteur d'une barre (avec son espace), largeur des libellés à gauche et de la colonne des
// pourcentages à droite, en pixels.
const ROW_HEIGHT_PX = 30
const LABEL_WIDTH_PX = 150
const PERCENT_WIDTH_PX = 64

// Couleurs lues dans la charte : barres en ink-soft (des données, pas un élément cliquable,
// donc pas l'accent) ; textes en ink. Les deux suivent le thème clair ou sombre.
const BAR_TOKEN = '--color-ink-soft'
const TEXT_TOKEN = '--color-ink'

interface ChartRow {
  name: string
  percent: number
  percentText: string
}

// Lignes du graphique : libellé français, longueur de la barre (0 à 100) et texte du
// pourcentage, dans l'ordre reçu (du plus probable au moins probable, garanti par l'API).
function toChartRows(probabilities: ClassProbability[]): ChartRow[] {
  const rows: ChartRow[] = []
  for (const item of probabilities) {
    const percent = item.probability * 100
    const percentText = formatPercent(item.probability)
    rows.push({ name: item.label_fr, percent, percentText })
  }
  return rows
}

// Barres horizontales de probabilité (EF-05, EF-06), axe de 0 à 100 %. Deux axes verticaux :
// les classes à gauche, les pourcentages à droite, alignés en colonne (un texte posé au bout
// d'une barre très courte se coupait sur deux lignes).
export default function ProbabilityChart({ probabilities }: { probabilities: ClassProbability[] }) {
  const rows = toChartRows(probabilities)
  const height = rows.length * ROW_HEIGHT_PX
  const barColor = readCssColor(BAR_TOKEN)
  const tick = { fill: readCssColor(TEXT_TOKEN), fontSize: 14 }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis
          yAxisId="classes"
          type="category"
          dataKey="name"
          width={LABEL_WIDTH_PX}
          tickLine={false}
          axisLine={false}
          tick={tick}
        />
        <YAxis
          yAxisId="percents"
          orientation="right"
          type="category"
          dataKey="percentText"
          width={PERCENT_WIDTH_PX}
          tickLine={false}
          axisLine={false}
          tick={tick}
        />
        <Bar yAxisId="classes" dataKey="percent" fill={barColor} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}
