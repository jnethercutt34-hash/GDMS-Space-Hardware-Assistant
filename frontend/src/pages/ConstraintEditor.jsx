import { useState } from 'react'
import { Upload, ShieldCheck, Download } from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import UploadZone from '../components/UploadZone'
import ConstraintTable from '../components/ConstraintTable'
import SectionLabel from '../components/SectionLabel'

export default function ConstraintEditor() {
  const [result, setResult]         = useState(null)
  const [isLoading, setIsLoading]   = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [error, setError]           = useState(null)

  const handleUpload = async (file) => {
    setIsLoading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/extract-constraints', { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Constraint extraction failed')
      }
      setResult(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleExport = async () => {
    if (!result?.constraints?.length) return
    setIsExporting(true)

    try {
      const res = await fetch('/api/export-ces-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ constraints: result.constraints }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Export failed')
      }

      const blob = await res.blob()
      downloadBlob(blob, 'xpedition_ces_update.py')
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
          Phase 3 · SI/PI Constraint Editor
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          SI/PI Constraint Extractor
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Upload a component datasheet to automatically extract signal integrity and power integrity
          constraints — impedance, timing, spacing, voltage levels — and export them to Xpedition CES.
        </p>
      </section>

      {/* Step 1 — Upload */}
      <section className="mb-14">
        <SectionLabel icon={<Upload className="h-4 w-4" />} step="1" label="Upload Datasheet" />
        <Card>
          <CardContent className="pt-6">
            <UploadZone onUpload={handleUpload} isLoading={isLoading} />
            {error && (
              <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
                <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">
                  Extraction Error
                </p>
                <p className="text-xs text-muted-foreground">{error}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Step 2 — Constraint Results */}
      {result && (
        <section className="mb-14">
          <SectionLabel icon={<ShieldCheck className="h-4 w-4" />} step="2" label="Extracted Constraints" />

          {/* Summary banner */}
          <div className="mb-4 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 flex items-center gap-3">
            <p className="text-xs text-primary font-semibold uppercase tracking-widest">
              {result.filename}
            </p>
            <span className="text-xs text-muted-foreground">
              {result.page_count} page{result.page_count !== 1 ? 's' : ''} scanned
            </span>
            <span className="text-xs text-muted-foreground">·</span>
            <span className="text-xs text-muted-foreground">
              {result.constraints.length} constraint{result.constraints.length !== 1 ? 's' : ''} found
            </span>
          </div>

          <Card>
            <CardContent className="pt-6">
              <ConstraintTable constraints={result.constraints} />

              {/* Export button */}
              {result.constraints.length > 0 && (
                <div className="mt-6 flex items-center gap-3 border-t border-border pt-6">
                  <Button onClick={handleExport} disabled={isExporting}>
                    <Download className="mr-2 h-4 w-4" />
                    {isExporting ? 'Generating…' : 'Export CES Script'}
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    Downloads a Python script for Xpedition Constraint Editor System
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

