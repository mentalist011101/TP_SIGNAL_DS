import { useState } from 'react'
import { describeApiError, useDeleteAnalysis } from '../../api/client.ts'

// Bouton secondaire de la charte. Pas de couleur danger : elle est réservée aux erreurs.
const BUTTON_CLASSES =
  'rounded-btn border border-rule-strong bg-card px-3 py-1 text-sm text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt disabled:opacity-50'

interface ConfirmDeleteProps {
  filename: string
  isPending: boolean
  errorMessage: string | null
  onConfirm: () => void
  onCancel: () => void
}

// Question de confirmation, avec les boutons Oui et Annuler.
function ConfirmDelete(props: ConfirmDeleteProps) {
  return (
    <div className="space-y-1">
      <p className="text-sm">Supprimer définitivement « {props.filename} » ?</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={`${BUTTON_CLASSES} font-semibold`}
          disabled={props.isPending}
          onClick={props.onConfirm}
        >
          Oui, supprimer
        </button>
        <button
          type="button"
          className={BUTTON_CLASSES}
          disabled={props.isPending}
          onClick={props.onCancel}
        >
          Annuler
        </button>
      </div>
      {props.errorMessage !== null && <p className="text-sm text-danger">{props.errorMessage}</p>}
    </div>
  )
}

interface DeleteControlProps {
  analysisId: string
  filename: string
}

// Supprimer en deux temps : un premier clic demande confirmation, le second supprime.
// La suppression est définitive (ligne en base et fichiers), d'où la confirmation (C22).
export default function DeleteControl({ analysisId, filename }: DeleteControlProps) {
  const [isConfirming, setIsConfirming] = useState(false)
  const deletion = useDeleteAnalysis()

  if (!isConfirming) {
    return (
      <button type="button" className={BUTTON_CLASSES} onClick={() => setIsConfirming(true)}>
        Supprimer
      </button>
    )
  }
  let errorMessage: string | null = null
  if (deletion.error !== null) {
    errorMessage = describeApiError(deletion.error)
  }
  return (
    <ConfirmDelete
      filename={filename}
      isPending={deletion.isPending}
      errorMessage={errorMessage}
      onConfirm={() => deletion.mutate(analysisId)}
      onCancel={() => setIsConfirming(false)}
    />
  )
}
