import { useState, useRef, DragEvent, ChangeEvent, FormEvent } from 'react'

type Status = 'idle' | 'loading' | 'success' | 'error'

const ACCEPTED = '.pdf,.txt,.csv,.tsv'

export default function App() {
  const [companyName, setCompanyName] = useState('')
  const [file, setFile]               = useState<File | null>(null)
  const [status, setStatus]           = useState<Status>('idle')
  const [errorMsg, setErrorMsg]       = useState('')
  const [dragging, setDragging]       = useState(false)
  const fileInputRef                  = useRef<HTMLInputElement>(null)

  // ── drag-and-drop ──────────────────────────────────────────────────────────
  const onDragOver  = (e: DragEvent) => { e.preventDefault(); setDragging(true) }
  const onDragLeave = ()              => setDragging(false)
  const onDrop      = (e: DragEvent) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files?.[0]
    if (f) setFile(f)
  }

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) setFile(f)
  }

  // ── submit ─────────────────────────────────────────────────────────────────
  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!file) { setErrorMsg('Please select a file.'); setStatus('error'); return }
    if (!companyName.trim()) { setErrorMsg('Please enter a company name.'); setStatus('error'); return }

    setStatus('loading'); setErrorMsg('')

    const form = new FormData()
    form.append('company_name', companyName.trim())
    form.append('file', file)

    try {
      const res = await fetch('/api/generate', { method: 'POST', body: form })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(detail.detail || 'Server error')
      }
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `${companyName.replace(/\s+/g, '_')}_equity_report.pdf`
      a.click()
      URL.revokeObjectURL(url)
      setStatus('success')
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Unknown error')
      setStatus('error')
    }
  }

  const reset = () => {
    setStatus('idle'); setFile(null); setErrorMsg('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div style={styles.page}>
      {/* ── header ── */}
      <header style={styles.header}>
        <div style={styles.headerInner}>
          <span style={styles.logo}>📊</span>
          <div>
            <h1 style={styles.headerTitle}>Equity Report Generator</h1>
            <p style={styles.headerSub}>AI-powered Geojit-style research reports in one click</p>
          </div>
        </div>
      </header>

      {/* ── main card ── */}
      <main style={styles.main}>
        <div style={styles.card}>
          <h2 style={styles.cardTitle}>Generate Research Report</h2>
          <p style={styles.cardDesc}>
            Upload a financial document (PDF, TXT, or CSV) and we'll extract key metrics,
            build charts, and produce a downloadable PDF report.
          </p>

          <form onSubmit={onSubmit} style={styles.form}>
            {/* company name */}
            <div style={styles.field}>
              <label htmlFor="company" style={styles.label}>Company Name *</label>
              <input
                id="company"
                type="text"
                value={companyName}
                onChange={e => setCompanyName(e.target.value)}
                placeholder="e.g. Reliance Industries"
                style={styles.input}
                disabled={status === 'loading'}
              />
            </div>

            {/* file upload */}
            <div style={styles.field}>
              <label style={styles.label}>Context Document *</label>
              <div
                style={{ ...styles.dropzone, ...(dragging ? styles.dropzoneActive : {}) }}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                {file ? (
                  <div style={styles.fileInfo}>
                    <span style={styles.fileIcon}>📄</span>
                    <div>
                      <p style={styles.fileName}>{file.name}</p>
                      <p style={styles.fileSize}>{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                    <button
                      type="button"
                      onClick={e => { e.stopPropagation(); reset() }}
                      style={styles.removeBtn}
                    >✕</button>
                  </div>
                ) : (
                  <div style={styles.dropzoneContent}>
                    <span style={styles.uploadIcon}>⬆️</span>
                    <p style={styles.dropText}>Drag & drop or <span style={styles.browseLink}>browse</span></p>
                    <p style={styles.dropHint}>Supports: PDF, TXT, CSV</p>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPTED}
                  onChange={onFileChange}
                  style={{ display: 'none' }}
                />
              </div>
            </div>

            {/* error */}
            {status === 'error' && (
              <div style={styles.errorBox}>
                <span>⚠️</span> {errorMsg}
              </div>
            )}

            {/* success */}
            {status === 'success' && (
              <div style={styles.successBox}>
                <span>✅</span> Report generated! Check your downloads folder.
              </div>
            )}

            {/* submit */}
            <button
              type="submit"
              disabled={status === 'loading'}
              style={{ ...styles.btn, ...(status === 'loading' ? styles.btnDisabled : {}) }}
            >
              {status === 'loading' ? (
                <span style={styles.spinnerRow}>
                  <span style={styles.spinner} /> Generating report…
                </span>
              ) : '⬇️  Generate & Download PDF'}
            </button>
          </form>
        </div>

        {/* ── info panels ── */}
        <div style={styles.infoGrid}>
          {[
            { icon: '🤖', title: 'AI Extraction', body: 'GPT-4o reads your document and maps financials to every template field automatically.' },
            { icon: '📑', title: 'Geojit-style Template', body: 'Matches the layout, sections, and tables of a professional equity research report.' },
            { icon: '📈', title: 'Charts Included', body: 'Revenue/PAT bar charts, margin trend lines, and quarterly breakdown generated automatically.' },
          ].map(({ icon, title, body }) => (
            <div key={title} style={styles.infoCard}>
              <span style={styles.infoIcon}>{icon}</span>
              <h3 style={styles.infoTitle}>{title}</h3>
              <p style={styles.infoBody}>{body}</p>
            </div>
          ))}
        </div>
      </main>

      <footer style={styles.footer}>
        Built for demonstration purposes only. Not investment advice.
      </footer>
    </div>
  )
}

// ── inline styles ──────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  page:   { display: 'flex', flexDirection: 'column', minHeight: '100vh' },
  header: { background: 'linear-gradient(135deg,#003366 0%,#1565C0 100%)', color: '#fff', padding: '24px 0' },
  headerInner: { maxWidth: 860, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 16 },
  logo:   { fontSize: 40 },
  headerTitle: { fontSize: 26, fontWeight: 700, margin: 0 },
  headerSub:   { fontSize: 14, opacity: 0.8, marginTop: 2 },

  main:  { flex: 1, maxWidth: 860, margin: '0 auto', padding: '32px 24px', width: '100%' },
  card:  { background: '#fff', borderRadius: 12, padding: 32, boxShadow: '0 2px 16px rgba(0,0,0,0.08)', marginBottom: 24 },
  cardTitle: { fontSize: 20, fontWeight: 700, marginBottom: 8, color: '#003366' },
  cardDesc:  { fontSize: 14, color: '#4a5568', marginBottom: 24, lineHeight: 1.6 },

  form:  { display: 'flex', flexDirection: 'column', gap: 20 },
  field: { display: 'flex', flexDirection: 'column', gap: 6 },
  label: { fontSize: 14, fontWeight: 600, color: '#2d3748' },
  input: {
    padding: '10px 14px', fontSize: 15, borderRadius: 8,
    border: '1.5px solid #cbd5e0', outline: 'none',
    transition: 'border-color .2s',
  },

  dropzone: {
    border: '2px dashed #cbd5e0', borderRadius: 10, padding: 28,
    cursor: 'pointer', textAlign: 'center', transition: 'all .2s',
    background: '#f7fafc',
  },
  dropzoneActive: { borderColor: '#1565C0', background: '#EBF4FF' },
  dropzoneContent: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 },
  uploadIcon: { fontSize: 32 },
  dropText:   { fontSize: 15, color: '#4a5568' },
  browseLink: { color: '#1565C0', fontWeight: 600 },
  dropHint:   { fontSize: 12, color: '#a0aec0' },

  fileInfo: { display: 'flex', alignItems: 'center', gap: 14 },
  fileIcon: { fontSize: 32 },
  fileName: { fontWeight: 600, fontSize: 14, color: '#2d3748' },
  fileSize: { fontSize: 12, color: '#718096' },
  removeBtn: {
    marginLeft: 'auto', background: 'none', border: 'none',
    fontSize: 18, cursor: 'pointer', color: '#a0aec0', padding: '0 4px',
  },

  errorBox:   { background: '#FFF5F5', border: '1px solid #FC8181', borderRadius: 8, padding: '12px 16px', color: '#C53030', fontSize: 14, display: 'flex', gap: 8, alignItems: 'center' },
  successBox: { background: '#F0FFF4', border: '1px solid #68D391', borderRadius: 8, padding: '12px 16px', color: '#276749', fontSize: 14, display: 'flex', gap: 8, alignItems: 'center' },

  btn: {
    padding: '14px 0', fontSize: 16, fontWeight: 700,
    background: 'linear-gradient(135deg,#003366,#1565C0)',
    color: '#fff', border: 'none', borderRadius: 8,
    cursor: 'pointer', letterSpacing: 0.3,
    transition: 'opacity .2s',
  },
  btnDisabled: { opacity: 0.6, cursor: 'not-allowed' },
  spinnerRow:  { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 },
  spinner: {
    width: 18, height: 18, border: '3px solid rgba(255,255,255,.4)',
    borderTopColor: '#fff', borderRadius: '50%',
    display: 'inline-block',
    animation: 'spin 0.8s linear infinite',
  },

  infoGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 16 },
  infoCard: { background: '#fff', borderRadius: 10, padding: 20, boxShadow: '0 1px 8px rgba(0,0,0,0.06)', display: 'flex', flexDirection: 'column', gap: 8 },
  infoIcon:  { fontSize: 28 },
  infoTitle: { fontSize: 15, fontWeight: 700, color: '#003366' },
  infoBody:  { fontSize: 13, color: '#718096', lineHeight: 1.5 },

  footer: { textAlign: 'center', padding: '16px 0', fontSize: 12, color: '#a0aec0', borderTop: '1px solid #e2e8f0', marginTop: 'auto' },
}
