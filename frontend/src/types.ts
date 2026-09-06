export type TriageRequest = {
  vehicle: { year: number; make: string; model: string; vehicle_id?: string }
  mileage: number
  customer_complaint: string
  service_advisor_notes: string
}

export type TriageResult = {
  run_id: number
  risk_level: 'routine' | 'priority' | 'safety_review'
  parsed_symptoms: string[]
  component: string
  missing_information: string[]
  matched_recalls: Array<Record<string, string>>
  matched_tsb: Array<Record<string, string | number>>
  prior_service_context: Array<Record<string, string | number>>
  recommended_inspection_steps: string[]
  human_review_required: boolean
  evidence_summary: string
  draft_work_order: string
  tools_used: string[]
}
