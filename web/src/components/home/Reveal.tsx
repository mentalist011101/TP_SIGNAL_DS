import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'

// Part de l'élément qui doit être visible avant qu'il apparaisse.
const VISIBLE_THRESHOLD = 0.15

interface RevealProps {
  children: ReactNode
  // Retard de l'apparition, pour faire entrer des cartes voisines l'une après l'autre.
  delayMs?: number
  className?: string
}

// Fait monter doucement son contenu la première fois qu'il entre à l'écran. Si le système
// demande moins d'animations, le contenu est affiché tel quel (motion-reduce).
export default function Reveal({ children, delayMs = 0, className = '' }: RevealProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const element = containerRef.current
    if (element === null) {
      return
    }
    // L'observateur prévient quand l'élément entre à l'écran ; on arrête ensuite d'observer.
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setIsVisible(true)
            observer.disconnect()
          }
        }
      },
      { threshold: VISIBLE_THRESHOLD },
    )
    observer.observe(element)
    return () => {
      observer.disconnect()
    }
  }, [])

  let stateClasses = 'translate-y-6 opacity-0'
  if (isVisible) {
    stateClasses = 'translate-y-0 opacity-100'
  }
  const delayStyle: CSSProperties = { transitionDelay: `${delayMs}ms` }
  return (
    <div
      ref={containerRef}
      style={delayStyle}
      className={`transition-[opacity,transform] duration-700 ease-out-soft motion-reduce:translate-y-0 motion-reduce:opacity-100 motion-reduce:transition-none ${stateClasses} ${className}`}
    >
      {children}
    </div>
  )
}
