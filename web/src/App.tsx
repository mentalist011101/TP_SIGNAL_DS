import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.tsx'
import AnalyzePage from './pages/AnalyzePage.tsx'
import ComparePage from './pages/ComparePage.tsx'
import HomePage from './pages/HomePage.tsx'
import HistoryPage from './pages/HistoryPage.tsx'
import LivePage from './pages/LivePage.tsx'
import ModelsPage from './pages/ModelsPage.tsx'
import ResultPage from './pages/ResultPage.tsx'
import SpeakersPage from './pages/SpeakersPage.tsx'

// Table des routes : l'accueil public sur la racine, puis l'application dans sa coque (menu à
// gauche), une page par fonctionnalité de la spécification (brique 7).
export default function App() {
  return (
    <Routes>
      <Route index element={<HomePage />} />
      <Route element={<Layout />}>
        <Route path="analyser" element={<AnalyzePage />} />
        <Route path="direct" element={<LivePage />} />
        <Route path="comparer" element={<ComparePage />} />
        <Route path="historique" element={<HistoryPage />} />
        <Route path="analyses/:analysisId" element={<ResultPage />} />
        <Route path="locuteurs" element={<SpeakersPage />} />
        <Route path="modeles" element={<ModelsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
