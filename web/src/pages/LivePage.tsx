import PagePlaceholder from '../components/PagePlaceholder.tsx'

export default function LivePage() {
  return (
    <PagePlaceholder
      title="Analyse en direct"
      description="Flux micro analysé par fenêtres glissantes : frise temporelle en direct, transcription par énoncé, latence et RTF."
      requirements={['EF-14']}
    />
  )
}
