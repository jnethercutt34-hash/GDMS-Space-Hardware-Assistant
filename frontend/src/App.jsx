import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import ComponentLibrarian from './pages/ComponentLibrarian'
import FpgaBridge from './pages/FpgaBridge'
import SiPiGuide from './pages/SiPiGuide'
import BlockDiagram from './pages/BlockDiagram'
import StackupDesigner from './pages/StackupDesigner'
import BomAnalyzer from './pages/BomAnalyzer'
import SchematicDrc from './pages/SchematicDrc'
import PartDetail from './pages/PartDetail'

export default function App() {
  return (
    <BrowserRouter>
      <div className="antialiased min-h-screen bg-background font-body">
        <Navbar />
        <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
          <Routes>
            <Route path="/"               element={<Home />} />
            <Route path="/librarian"      element={<ComponentLibrarian />} />
            <Route path="/part/:partNumber" element={<PartDetail />} />
            <Route path="/block-diagram"  element={<BlockDiagram />} />
            <Route path="/stackup"        element={<StackupDesigner />} />
            <Route path="/constraints"    element={<SiPiGuide />} />
            <Route path="/drc"            element={<SchematicDrc />} />
            <Route path="/fpga"           element={<FpgaBridge />} />
            <Route path="/bom"            element={<BomAnalyzer />} />
            {/* Legacy /com route → redirect to SI/PI Guide */}
            <Route path="/com"            element={<Navigate to="/constraints" replace />} />
            {/* Catch-all → home */}
            <Route path="*"              element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
