import { useState } from 'react'
import Navbar from './components/Navbar'
import ComponentLibrarian from './pages/ComponentLibrarian'
import FpgaBridge from './pages/FpgaBridge'

export default function App() {
  const [currentPage, setCurrentPage] = useState('librarian')

  return (
    <div className="antialiased min-h-screen bg-background font-body">
      <Navbar currentPage={currentPage} setCurrentPage={setCurrentPage} />
      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        {currentPage === 'librarian' && <ComponentLibrarian />}
        {currentPage === 'fpga'      && <FpgaBridge />}
      </main>
    </div>
  )
}
