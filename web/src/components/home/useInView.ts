import { useEffect, useRef, useState } from 'react'

// Part de l'élément qui doit être visible pour qu'il compte comme « à l'écran ».
const VISIBLE_THRESHOLD = 0.3

// Vrai dès que l'élément entre à l'écran (puis reste vrai) : sert à lancer une animation au
// moment où on la voit, et pas au chargement de la page.
export function useInView<T extends Element>() {
  const ref = useRef<T>(null)
  const [isInView, setIsInView] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (element === null) {
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setIsInView(true)
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

  return { ref, isInView }
}
