import React, { useState } from 'react'
import { Filter, ArrowUpRight } from 'lucide-react'
import type { Incident } from '../types/incident'

interface IncidentsListProps {
  incidents: Incident[]
  pastIncidents: any[]
  onSelectIncident: (id: string) => void
}

export const IncidentsList: React.FC<IncidentsListProps> = ({
  incidents,
  pastIncidents,
  onSelectIncident,
}) => {
  const [filterSeverity, setFilterSeverity] = useState<string>('all')

  // Combine active and past
  const allItems = [
    ...incidents,
    ...pastIncidents.map((p) => ({
      incident_id: p.incident_id,
      title: p.title,
      service: p.service || 'checkout-service',
      severity: (p.severity || 'P1') as 'P0' | 'P1' | 'P2' | 'P3',
      status: 'resolved' as const,
      current_stage: 'completed',
      started_at: p.occurred_at || new Date().toISOString(),
      affected_services: [p.service || 'checkout-service'],
      stages: [],
      evidence: { logs: [], metrics: [], service_health: {}, deployment_history: {} },
      similar_past_incidents: [],
      runbook: { title: '', content: '' },
      decision: {
        hypothesis: p.root_cause || '',
        root_cause: p.root_cause || '',
        recommended_action: p.resolution || 'rollback',
        confidence: p.confidence || 0.9,
        provider: 'chromadb',
        model: 'sentence-transformers',
      },
      approval: { status: 'approved' as const, action: p.resolution || 'rollback', service: p.service || 'checkout-service', confidence: p.confidence || 0.9 },
      remediation: { attempted: true, result: p.resolution || 'rollback', is_simulated: true },
      verification: { before: {}, after: {}, passed: true },
      report: p.root_cause || '',
      source: 'memory',
    })),
  ]

  const filtered = allItems.filter((item) => {
    if (filterSeverity === 'all') return true
    return item.severity === filterSeverity
  })

  return (
    <div>
      <div className="card" style={{ marginBottom: '20px', padding: '16px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Filter size={15} style={{ color: 'var(--text-muted)' }} />
            <span style={{ fontSize: '13px', fontWeight: 500 }}>Filter by Severity:</span>
            {['all', 'P0', 'P1', 'P2'].map((sev) => (
              <button
                key={sev}
                className={`btn btn-sm ${filterSeverity === sev ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setFilterSeverity(sev)}
              >
                {sev.toUpperCase()}
              </button>
            ))}
          </div>

          <span style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>
            Showing {filtered.length} total incidents ({incidents.length} active, {pastIncidents.length} stored in memory)
          </span>
        </div>
      </div>

      <div className="card">
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Incident ID</th>
                <th>Title / Description</th>
                <th>Service</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Action</th>
                <th>Confidence</th>
                <th>Source</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((inc) => (
                <tr key={inc.incident_id} onClick={() => onSelectIncident(inc.incident_id)}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{inc.incident_id}</td>
                  <td style={{ maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {inc.title}
                  </td>
                  <td>{inc.service}</td>
                  <td>
                    <span className={`badge badge-${inc.severity}`}>{inc.severity}</span>
                  </td>
                  <td>
                    <span className={`badge badge-${inc.status}`}>
                      {inc.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td style={{ fontWeight: 500 }}>
                    {inc.decision?.recommended_action?.toUpperCase() || '—'}
                  </td>
                  <td>
                    {inc.decision?.confidence ? `${(inc.decision.confidence * 100).toFixed(0)}%` : '—'}
                  </td>
                  <td style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    {inc.source === 'memory' ? 'Memory' : 'Active'}
                  </td>
                  <td>
                    <ArrowUpRight size={14} style={{ color: 'var(--text-muted)' }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
