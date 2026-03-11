import { useState } from 'react'
import { FileSpreadsheet, GitCompare, Download } from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import DualCsvUpload from '../components/DualCsvUpload'
import DeltaTable from '../components/DeltaTable'
import SectionLabel from '../components/SectionLabel'

export default function FpgaBridge() {
  const [deltaResult, setDeltaResult] = useState(null)
  const [isLoading, setIsLoading]     = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [error, setError]             = useState(null)

  const handleCompare = async (baselineFile, newFile) => {
    setIsLoading(true)
    setError(null)
    setDeltaResult(null)

    const formData = new FormData()
    formData.append('baseline_csv', baselineFile)
    formData.append('new_csv', newFile)

    try {
      const res = await fetch('/api/compare-fpga-pins', { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Comparison failed')
      }
      setDeltaResult(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleExport = async () => {
    if (!deltaResult?.swapped_pins?.length) return
    setIsExporting(true)

    try {
      const res = await fetch('/api/export-io-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ swapped_pins: deltaResult.swapped_pins }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Export failed')
      }

      const blob = await res.blob()
      downloadBlob(blob, 'xpedition_pin_update.py')
    } catch (e) {
      setError(e.message)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div>
      {/* Hero */}
      <section className="mb-14">
        <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
          Step 6 · FPGA I/O Bridge
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          FPGA Pin Delta Analyzer
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Compare baseline and updated FPGA pinout CSVs to detect pin swaps and bank migrations,
          with AI risk assessment for every change.
        </p>
      </section>

      {/* Step 1 — Upload */}
      <section className="mb-14">
        <SectionLabel icon={<FileSpreadsheet className="h-4 w-4" />} step="1" label="Upload Pinout CSV Files" />

        <div className="mb-4 rounded-md border border-primary/20 bg-primary/5 px-3 py-2">
          <p className="text-xs text-primary font-semibold uppercase tracking-widest mb-0.5">
            Required Columns
          </p>
          <p className="text-xs text-muted-foreground">
            Both CSVs must contain:{' '}
            <code className="font-mono text-primary/80">Signal_Name</code>,{' '}
            <code className="font-mono text-primary/80">Pin</code>,{' '}
            <code className="font-mono text-primary/80">Bank</code>
          </p>
        </div>

        <Card>
          <CardContent className="pt-6">
            <DualCsvUpload onSubmit={handleCompare} isLoading={isLoading} />
            {error && (
              <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
                <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">
                  Comparison Error
                </p>
                <p className="text-xs text-muted-foreground">{error}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Step 2 — Delta Results */}
      {deltaResult && (
        <section className="mb-14">
          <SectionLabel icon={<GitCompare className="h-4 w-4" />} step="2" label="Pin Delta Results" />
          <Card>
            <CardContent className="pt-6">
              <DeltaTable data={deltaResult} />

              {/* Export button — only shown when there are swaps */}
              {deltaResult.total_swaps > 0 && (
                <div className="mt-6 flex items-center gap-3 border-t border-border pt-6">
                  <Button onClick={handleExport} disabled={isExporting}>
                    <Download className="mr-2 h-4 w-4" />
                    {isExporting ? 'Generating…' : 'Export Xpedition Update Script'}
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    Downloads a Python script for Xpedition I/O Designer
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  )
}

