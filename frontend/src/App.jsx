import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import ComponentLibrarian from './pages/ComponentLibrarian'
import FpgaBridge from './pages/FpgaBridge'
import ConstraintEditor from './pages/ConstraintEditor'
import BlockDiagram from './pages/BlockDiagram'
import ComAnalysis from './pages/ComAnalysis'
import BomAnalyzer from './pages/BomAnalyzer'
import SchematicDrc from './pages/SchematicDrc'

export default function App() {
  return (
    <BrowserRouter>
      <div className="antialiased min-h-screen bg-background font-body">
        <Navbar />
        <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
          <Routes>
            <Route path="/"               element={<ComponentLibrarian />} />
            <Route path="/fpga"           element={<FpgaBridge />} />
            <Route path="/constraints"    element={<ConstraintEditor />} />
            <Route path="/block-diagram"  element={<BlockDiagram />} />
            <Route path="/com"            element={<ComAnalysis />} />
            <Route path="/bom"            element={<BomAnalyzer />} />
            <Route path="/drc"            element={<SchematicDrc />} />
            {/* Catch-all → home */}
            <Route path="*"              element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
