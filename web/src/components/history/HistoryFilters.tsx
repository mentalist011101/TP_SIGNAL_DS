import type { ChangeEvent } from 'react'
import type { DateFilter, HistoryFilterValues, StatusFilter } from './historyFilters.ts'

interface FilterOption {
  value: string
  label: string
}

const STATUS_OPTIONS: FilterOption[] = [
  { value: 'all', label: 'Tous les statuts' },
  { value: 'done', label: 'Terminées' },
  { value: 'running', label: 'En cours' },
  { value: 'failed', label: 'En échec' },
]

const DATE_OPTIONS: FilterOption[] = [
  { value: 'all', label: 'Toutes les dates' },
  { value: 'today', label: 'Aujourd’hui' },
  { value: 'week', label: '7 derniers jours' },
  { value: 'month', label: '30 derniers jours' },
]

const SELECT_CLASSES = 'rounded-btn border border-rule-strong bg-card px-2 py-1 text-ink'

interface FilterSelectProps {
  label: string
  value: string
  options: FilterOption[]
  onChange: (value: string) => void
}

// Une liste déroulante précédée de son libellé.
function FilterSelect({ label, value, options, onChange }: FilterSelectProps) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    onChange(event.target.value)
  }
  return (
    <label className="flex items-center gap-2">
      {label} :
      <select className={SELECT_CLASSES} value={value} onChange={handleChange}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

interface HistoryFiltersProps {
  filters: HistoryFilterValues
  onFiltersChange: (filters: HistoryFilterValues) => void
}

// Filtres par statut et par période. Chaque changement renvoie un nouvel objet filtres.
// Les valeurs viennent des listes ci-dessus : la conversion de type est donc sûre.
export default function HistoryFilters({ filters, onFiltersChange }: HistoryFiltersProps) {
  function handleStatusChange(value: string) {
    const status = value as StatusFilter
    onFiltersChange({ status, date: filters.date })
  }

  function handleDateChange(value: string) {
    const date = value as DateFilter
    onFiltersChange({ status: filters.status, date })
  }

  return (
    <div className="flex flex-wrap items-center gap-4 text-sm">
      <FilterSelect
        label="Statut"
        value={filters.status}
        options={STATUS_OPTIONS}
        onChange={handleStatusChange}
      />
      <FilterSelect
        label="Période"
        value={filters.date}
        options={DATE_OPTIONS}
        onChange={handleDateChange}
      />
    </div>
  )
}
