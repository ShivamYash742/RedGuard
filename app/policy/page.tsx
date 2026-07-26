"use client"
import { useState, useEffect } from 'react'

export default function PolicyEditor() {
  const [yaml, setYaml] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')

  useEffect(() => {
    async function loadPolicy() {
      try {
        const res = await fetch('/api/policy')
        if (res.ok) {
          const data = await res.json()
          setYaml(data.yaml || '')
        }
      } catch (err) {
        console.error("Failed to load policy", err)
      } finally {
        setLoading(false)
      }
    }
    loadPolicy()
  }, [])

  const savePolicy = async () => {
    setSaving(true)
    setMessage('')
    try {
      const res = await fetch('/api/policy', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml })
      })
      if (res.ok) {
        setMessage('Policy saved successfully.')
      } else {
        setMessage('Failed to save policy.')
      }
    } catch (err) {
      setMessage('Error saving policy.')
      console.error(err)
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(''), 3000)
    }
  }

  if (loading) return <div>Loading policy...</div>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 600 }}>Security Policy</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {message && <span style={{ color: message.includes('success') ? 'var(--accent-green)' : 'var(--accent-red)' }}>{message}</span>}
          <button 
            className="btn-primary" 
            onClick={savePolicy} 
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Policy'}
          </button>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 200px)' }}>
        <div style={{ marginBottom: '1rem', color: 'var(--text-secondary)' }}>
          Edit the active <code>policy.yaml</code> file. Changes will take effect on the next scan.
        </div>
        <textarea
          value={yaml}
          onChange={e => setYaml(e.target.value)}
          style={{
            flex: 1,
            width: '100%',
            background: 'rgba(0,0,0,0.3)',
            border: '1px solid var(--panel-border)',
            borderRadius: '8px',
            color: 'var(--text-primary)',
            fontFamily: 'monospace',
            fontSize: '0.875rem',
            padding: '1rem',
            resize: 'none',
            outline: 'none'
          }}
        />
      </div>
    </div>
  )
}
