export interface StageItem {
  id: string
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  timestamp?: string | null
}

export interface LogEntry {
  timestamp: string
  service: string
  level: string
  message: string
}

export interface MetricEntry {
  name: string
  value: number | string
  unit: string
  service: string
}

export interface EvidenceData {
  logs: LogEntry[]
  metrics: MetricEntry[]
  service_health: Record<string, string>
  deployment_history: Record<string, {
    version: string
    previous_version?: string
    deployed_minutes_ago?: number
  }>
}

export interface SimilarIncident {
  incident_id: string
  title: string
  service?: string
  severity?: string
  similarity?: number
  root_cause?: string
  resolution?: string
  confidence?: number
}

export interface RunbookData {
  title: string
  content: string
}

export interface DecisionData {
  hypothesis: string
  root_cause: string
  recommended_action: string
  confidence: number
  provider: string
  model: string
  action_plan?: string[]
  evidence_summary?: string
  risk_assessment?: string
}

export interface ApprovalData {
  status: 'pending' | 'approved' | 'denied'
  action: string
  service: string
  confidence: number
  resolved_at?: string | null
}

export interface RemediationData {
  attempted: boolean
  result: string
  action?: string
  service?: string
  is_simulated: boolean
}

export interface VerificationData {
  before: {
    service_health?: Record<string, string>
    error_rates?: Record<string, string | number>
  }
  after: {
    service_health?: Record<string, string>
    error_rates?: Record<string, string | number>
  }
  passed: boolean
}

export interface Incident {
  incident_id: string
  title: string
  service: string
  severity: 'P0' | 'P1' | 'P2' | 'P3'
  status: 'investigating' | 'awaiting_approval' | 'mitigating' | 'resolved' | 'rejected' | 'escalated' | 'error'
  current_stage: string
  started_at: string
  resolved_at?: string | null
  duration_seconds?: number | null
  affected_services: string[]
  stages: StageItem[]
  evidence: EvidenceData
  similar_past_incidents: SimilarIncident[]
  runbook: RunbookData
  decision: DecisionData
  approval: ApprovalData
  remediation: RemediationData
  verification: VerificationData
  report: string
  error?: string
  source?: string
}

export interface SystemStatus {
  status: 'healthy' | 'degraded'
  api: string
  redis: string
  groq: string
  memory: string
  chromadb?: string
  agent: string
  memory_incidents: number
  decision_provider: string
  version: string
  timestamp: string
}

export interface RunbookSummary {
  filename: string
  title: string
  path: string
  size_bytes: number
  summary: string
}

export interface StoredMemoryIncident {
  incident_id: string
  title: string
  service: string
  severity: string
  occurred_at: string
  root_cause: string
  resolution: string
  confidence: number
  document?: string
}
