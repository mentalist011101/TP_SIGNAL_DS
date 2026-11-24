import { Link } from 'react-router-dom'
import { WaveIcon } from './icons.tsx'

// Logo : la forme d'onde dans un carré, puis le nom en serif. Il ramène à l'accueil.
export default function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2.5 text-ink">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-on-accent">
        <WaveIcon className="h-5 w-5" />
      </span>
      <span className="font-display text-2xl">EchoLens</span>
    </Link>
  )
}
