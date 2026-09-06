import type { TriageRequest, TriageResult } from './types'

const API = 'http://localhost:8000/api'

export async function runTriage(payload: TriageRequest): Promise<TriageResult> {
  const response = await fetch(`${API}/triage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Triage request failed')
  }
  return response.json()
}

export async function approveWorkOrder(runId: number, workOrder: string) {
  const response = await fetch(`${API}/triage/${runId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ work_order: workOrder }),
  })
  if (!response.ok) throw new Error('Approval failed')
  return response.json()
}
