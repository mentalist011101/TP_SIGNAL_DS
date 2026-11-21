import type { ChangeEvent } from 'react'
import type { DateFilter, HistoryFilterValues, StatusFilter } from './historyFilters.ts'

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'Toutes' },
  { value: 'done', label: 'Terminées' },
  { value: 'running', label: 'En cours' },
  { value: 'failed', label: 'En échec' },
]

const DATE_OPTIONS: { value: DateFilter; label: string }[] = [
  { value: 'all', label: 'Toutes les dates' },
  { value: 'today', label: 'Aujourd’hui' },
  { value: 'week', label: '7 derniers jours' },
  { value: 'month', label: '30 derniers jours' },
]

const FIELD_CLASSES = 'rounded-btn border border-rule-strong bg-card px-3 py-1.5 text-sm text-ink'

// Segment du filtre de statut : même style que le choix du profil sur la page Analyser.
const SEGMENT_CLASSES =
  'cursor-pointer rounded-btn px-3 py-1 text-center text-sm text-ink-soft transition-colors duration-200 ease-out-soft hover:text-ink has-checked:bg-ink has-checked:font-semibold has-checked:text-paper has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-accent-ink'

interface HistoryFiltersProps {
  filters: HistoryFilterValues
  onFiltersChange: (filters: HistoryFilterValues) => void
}

// Recherche par nom, statut en segments, période en liste. Chaque changement renvoie un
// nouvel objet filtres.
export default function HistoryFilters({ filters, onFiltersChange }: HistoryFiltersProps) {
  function handleQueryChange(event: ChangeEvent<HTMLInputElement>) {
    onFiltersChange({ ...filters, query: event.target.value })
  }

  function handleStatusChange(status: StatusFilter) {
    onFiltersChange({ ...filters, status })
  }

  // Les valeurs viennent de DATE_OPTIONS : la conversion de type est donc sûre.
  function handleDateChange(event: ChangeEvent<HTMLSelectElement>) {
    const date = event.target.value as DateFilter
    onFiltersChange({ ...filters, date })
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="search"
        className={`${FIELD_CLASSES} min-w-0 flex-1 basis-56`}
        placeholder="Rechercher un fichier…"
        aria-label="Rechercher un fichier"
        value={filters.query}
        onChange={handleQueryChange}
      />
      <fieldset className="flex flex-wrap gap-1 rounded-btn border border-rule-strong bg-card p-1">
        <legend className="sr-only">Statut</legend>
        {STATUS_OPTIONS.map((option) => (
          <label key={option.value} className={SEGMENT_CLASSES}>
            <input
              type="radio"
              name="status-filter"
              className="sr-only"
              checked={filters.status === option.value}
              onChange={() => handleStatusChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </fieldset>
      <select
        className={FIELD_CLASSES}
        aria-label="Période"
        value={filters.date}
        onChange={handleDateChange}
      >
        {DATE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}
