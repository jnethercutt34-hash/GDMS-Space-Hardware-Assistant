/**
 * Trigger a browser file download from a Blob.
 *
 * @param {Blob}   blob     - The file content.
 * @param {string} filename - The suggested download filename.
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
