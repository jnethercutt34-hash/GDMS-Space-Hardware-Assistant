import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { TableIcon, CheckCircle2 } from 'lucide-react'
import { Button } from './ui/button'

function CsvDropZone({ label, sublabel, file, onFile, disabled }) {
  const onDrop = useCallback(
    (accepted) => { if (accepted.length) onFile(accepted[0]) },
    [onFile]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'application/vnd.ms-excel': ['.csv'], 'text/plain': ['.csv'] },
    multiple: false,
    disabled,
  })

  const hasFile = Boolean(file)

  return (
    <div className="flex-1 flex flex-col gap-2">
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{label}</p>
      <div
        {...getRootProps()}
        className={[
          'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors duration-200 flex-1',
          hasFile
            ? 'border-primary/50 bg-primary/5'
            : isDragActive
              ? 'border-primary bg-primary/5'
              : 'border-border hover:border-primary/50 hover:bg-secondary/30',
          disabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : '',
        ].join(' ')}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-2">
          {hasFile ? (
            <CheckCircle2 className="h-8 w-8 text-primary" />
          ) : (
            <TableIcon className={`h-8 w-8 ${isDragActive ? 'text-primary' : 'text-muted-foreground'}`} />
          )}
          {hasFile ? (
            <>
              <p className="text-primary font-semibold text-sm truncate max-w-full px-2">
                {file.name}
              </p>
              <p className="text-muted-foreground text-xs">Click or drop to replace</p>
            </>
          ) : (
            <>
              <p className="text-foreground text-sm font-medium">{sublabel}</p>
              <p className="text-muted-foreground text-xs">Drag &amp; drop or click to browse — CSV only</p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function DualCsvUpload({ onSubmit, isLoading }) {
  const [baselineFile, setBaselineFile] = useState(null)
  const [newFile, setNewFile]           = useState(null)

  const canSubmit = baselineFile && newFile && !isLoading

  const handleSubmit = () => {
    if (canSubmit) onSubmit(baselineFile, newFile)
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        <CsvDropZone
          label="Baseline Pinout CSV"
          sublabel="Current Xpedition schematic pinout"
          file={baselineFile}
          onFile={setBaselineFile}
          disabled={isLoading}
        />
        <CsvDropZone
          label="New Vivado CSV"
          sublabel="Updated export from the FPGA team"
          file={newFile}
          onFile={setNewFile}
          disabled={isLoading}
        />
      </div>

      <div className="flex justify-end">
        <Button onClick={handleSubmit} disabled={!canSubmit}>
          {isLoading ? 'Calculating…' : 'Calculate Pin Deltas →'}
        </Button>
      </div>
    </div>
  )
}
