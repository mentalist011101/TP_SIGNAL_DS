import PagePlaceholder from '../components/PagePlaceholder.tsx'

export default function SpeakersPage() {
  return (
    <PagePlaceholder
      title="Locuteurs"
      description="Enregistrement des voix (avec consentement) pour l'identification du locuteur."
      requirements={['EF-11']}
    />
  )
}
