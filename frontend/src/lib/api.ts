import type { Incident, SystemStatus, RunbookSummary, StoredMemoryIncident } from '../types/incident'

const API_BASE = '' // relative, proxied by Vite to http://127.0.0.1:8000

export async function fetchHealth(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error(`Healthcheck failed: ${res.statusText}`)
  return res.json()
}

export async function fetchIncidents(): Promise<{
  active: Incident[]
  past: any[]
  total_active: number
  total_memory: number
}> {
  const res = await fetch(`${API_BASE}/incidents`)
  if (!res.ok) throw new Error(`Failed to load incidents: ${res.statusText}`)
  return res.json()
}

export async function fetchIncident(incidentId: string): Promise<Incident> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`)
  if (!res.ok) throw new Error(`Failed to load incident ${incidentId}: ${res.statusText}`)
  return res.json()
}

export async function triggerIncident(payload: {
  title: string
  service: string
  metric: string
  value: string
  threshold: string
  severity?: string
  affected_services?: string[]
  environment?: string
}): Promise<{ incident_id: string; status: string; poll_url: string }> {
  const res = await fetch(`${API_BASE}/incidents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to trigger incident: ${res.statusText}`)
  return res.json()
}

export async function triggerTestIncident(severity: 'P0' | 'P1' | 'P2'): Promise<{
  incident_id: string
  status: string
  poll_url: string
}> {
  const res = await fetch(`${API_BASE}/incidents/test/${severity}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Failed to fire ${severity} test alert: ${res.statusText}`)
  return res.json()
}

export async function approveRemediation(incidentId: string): Promise<{
  incident_id: string
  status: string
  message: string
}> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/approve`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Approval failed: ${res.statusText}`)
  return res.json()
}

export async function rejectRemediation(incidentId: string): Promise<{
  incident_id: string
  status: string
  message: string
}> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/reject`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Rejection failed: ${res.statusText}`)
  return res.json()
}

export function getReportDownloadUrl(incidentId: string): string {
  return `${API_BASE}/incidents/${incidentId}/report`
}

export async function fetchRunbooks(): Promise<{ runbooks: RunbookSummary[]; total: number }> {
  const res = await fetch(`${API_BASE}/runbooks`)
  if (!res.ok) throw new Error(`Failed to load runbooks: ${res.statusText}`)
  return res.json()
}

export async function fetchRunbook(filename: string): Promise<{ filename: string; content: string }> {
  const res = await fetch(`${API_BASE}/runbooks/${filename}`)
  if (!res.ok) throw new Error(`Failed to load runbook ${filename}: ${res.statusText}`)
  return res.json()
}

export async function fetchMemory(query?: string): Promise<{ incidents: StoredMemoryIncident[]; total: number }> {
  const url = query ? `${API_BASE}/memory?query=${encodeURIComponent(query)}` : `${API_BASE}/memory`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to load memory: ${res.statusText}`)
  return res.json()
}
