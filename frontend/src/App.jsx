import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router'
import { AuthProvider } from './auth/AuthContext'
import AppShell from './components/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import AuthPage from './pages/AuthPage'
import BusinessTask from './pages/BusinessTask'
import BusinessWorkspace from './pages/BusinessWorkspace'
import Catalog from './pages/Catalog'
import TaskDetail from './pages/TaskDetail'
import TaskDraft from './pages/TaskDraft'
import TeamDirectory from './pages/TeamDirectory'
import TeamDetail from './pages/TeamDetail'
import ProposalReview from './pages/ProposalReview'
import MyProposals from './pages/MyProposals'

function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/tasks" replace />} />
        <Route path="tasks" element={<Catalog />} />
        <Route path="tasks/:taskId" element={<TaskDetail />} />
        <Route path="teams" element={<TeamDirectory />} />
        <Route path="teams/:teamId" element={<TeamDetail />} />
        <Route path="login" element={<AuthPage mode="login" />} />
        <Route path="register" element={<AuthPage mode="register" />} />
        <Route element={<ProtectedRoute />}>
          <Route path="business" element={<BusinessWorkspace />} />
          <Route path="business/tasks/new" element={<TaskDraft />} />
          <Route path="business/tasks/:taskId" element={<BusinessTask />} />
          <Route path="business/tasks/:taskId/proposals" element={<ProposalReview />} />
          <Route path="proposals/mine" element={<MyProposals />} />
        </Route>
        <Route path="*" element={<section className="page"><div className="feedback feedback-error" role="alert"><strong>Page not found</strong><span>That BriefForge page does not exist.</span></div><Link to="/tasks">Browse tasks</Link></section>} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return <BrowserRouter><AuthProvider><AppRoutes /></AuthProvider></BrowserRouter>
}
