import React, { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import type { StoredMemoryIncident } from '../types/incident'
import { fetchMemory } from '../lib/api'

export const MemoryPage: React.FC = () => {
  const [incidents, setIncidents] = useState<StoredMemoryIncident[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)

  const loadMemory = (query?: string) => {
    setIsSearching(true)
    fetchMemory(query)
      .then((data) => {
        setIncidents(data.incidents || [])
        setLoading(false)
        setIsSearching(false)
      })
      .catch((err) => {
        console.error(err)
        setLoading(false)
        setIsSearching(false)
      })
  }

  useEffect(() => {
    loadMemory()
  }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    loadMemory(searchQuery)
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: '24px', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '6px' }}>Incident Vector Memory</h2>
            <p style={{ fontSize: '13.5px', color: 'var(--text-secondary)' }}>
              Past resolved incidents stored in ChromaDB with local sentence embeddings (<code>all-MiniLM-L6-v2</code>).
            </p>
          </div>

          <form onSubmit={handleSearch} style={{ display: 'flex', gap: '8px' }}>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                className="form-input"
                style={{ width: '280px', paddingLeft: '32px' }}
                placeholder="Search semantic memory..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <Search
                size={14}
                style={{ position: 'absolute', left: '10px', top: '11px', color: 'var(--text-muted)' }}
              />
            </div>
            <button type="submit" className="btn btn-secondary btn-sm" disabled={isSearching}>
              {isSearching ? 'Searching...' : 'Search'}
            </button>
            {searchQuery && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setSearchQuery('')
                  loadMemory()
                }}
              >
                Clear
              </button>
            )}
          </form>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center' }}>Loading incident memory...</div>
      ) : incidents.length === 0 ? (
        <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          No memory records match this query.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '16px' }}>
          {incidents.map((inc) => (
            <div
              key={inc.incident_id}
              className="card"
              style={{
                padding: '20px',
                marginBottom: 0,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '13px' }}>
                    {inc.incident_id}
                  </span>
                  <span className={`badge badge-${inc.severity}`}>{inc.severity}</span>
                </div>

                <h3 style={{ fontSize: '14.5px', fontWeight: 600, marginBottom: '6px' }}>{inc.title}</h3>

                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                  Service: <strong>{inc.service}</strong>
                </div>

                <div style={{ marginBottom: '10px' }}>
                  <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                    Root Cause
                  </span>
                  <p style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '2px', lineHeight: 1.4 }}>
                    {inc.root_cause || 'Deployment connection pool exhaustion'}
                  </p>
                </div>

                <div>
                  <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                    Resolution
                  </span>
                  <p style={{ fontSize: '13px', color: '#15803D', fontWeight: 500, marginTop: '2px' }}>
                    {inc.resolution || 'Rolled back deployment to previous version'}
                  </p>
                </div>
              </div>

              <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '16px', paddingTop: '10px', display: 'flex', justifyContent: 'space-between', fontSize: '11.5px', color: 'var(--text-muted)' }}>
                <span>Confidence: {(inc.confidence * 100).toFixed(0)}%</span>
                <span>{inc.occurred_at ? new Date(inc.occurred_at).toLocaleDateString() : 'Historical'}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
