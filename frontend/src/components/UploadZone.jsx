import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { FileText, Loader2 } from 'lucide-react'

export default function UploadZone({ onUpload, isLoading }) {
  const onDrop = useCallback(
    (acceptedFiles) => {
      if (acceptedFiles.length > 0) onUpload(acceptedFiles[0])
    },
    [onUpload]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isLoading,
  })

  return (
    <div
      {...getRootProps()}
      className={[
        'border-2 border-dashed rounded-lg p-14 text-center cursor-pointer transition-colors duration-200',
        isDragActive
          ? 'border-primary bg-primary/5'
          : 'border-border hover:border-primary/50 hover:bg-secondary/30',
        isLoading ? 'opacity-50 cursor-not-allowed pointer-events-none' : '',
      ].join(' ')}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3">
        {isLoading ? (
          <Loader2 className="h-10 w-10 text-primary animate-spin" />
        ) : (
          <FileText className={`h-10 w-10 ${isDragActive ? 'text-primary' : 'text-muted-foreground'}`} />
        )}
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Extracting PDF text…</p>
        ) : isDragActive ? (
          <p className="text-primary font-semibold">Drop the PDF here</p>
        ) : (
          <>
            <p className="text-foreground font-medium">
              Drag &amp; drop a component datasheet PDF
            </p>
            <p className="text-muted-foreground text-sm">or click to browse — PDF files only</p>
          </>
        )}
      </div>
    </div>
  )
}
