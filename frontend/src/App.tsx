import { FormEvent, useMemo, useState } from 'react'
import { approveWorkOrder, runTriage } from './api'
import type { TriageRequest, TriageResult } from './types'

const demos = {
  civic: { year: 2021, make: 'Honda', model: 'Civic', vehicle_id: 'HC-2021-001' },
  rav4: { year: 2022, make: 'Toyota', model: 'RAV4', vehicle_id: 'TR-2022-002' },
}

function App() {
  const [vehicleKey, setVehicleKey] = useState<'civic' | 'rav4'>('civic')
  const [mileage, setMileage] = useState(52100)
  const [complaint, setComplaint] = useState('Grinding noise when braking and the ABS light came on yesterday.')
  const [notes, setNotes] = useState('Customer says braking feel may be slightly different.')
  const [result, setResult] = useState<TriageResult | null>(null)
  const [workOrder, setWorkOrder] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const vehicle = useMemo(() => demos[vehicleKey], [vehicleKey])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setLoading(true); setMessage(''); setResult(null)
    const payload: TriageRequest = { vehicle, mileage, customer_complaint: complaint, service_advisor_notes: notes }
    try {
      const data = await runTriage(payload)
      setResult(data); setWorkOrder(data.draft_work_order)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Request failed')
    } finally { setLoading(false) }
  }

  async function approve() {
    if (!result) return
    await approveWorkOrder(result.run_id, workOrder)
    setMessage('Work order approved and saved.')
  }

  return <main className="shell">
    <header>
      <p className="eyebrow">SERVICE ADVISOR CONSOLE</p>
      <h1>Vehicle Service Triage Agent</h1>
      <p className="sub">Evidence-grounded intake across recalls, manufacturer technical communications, and prior service history.</p>
    </header>

    <section className="grid">
      <form className="card intake" onSubmit={submit}>
        <h2>New Service Intake</h2>
        <label>Demo vehicle
          <select value={vehicleKey} onChange={e => setVehicleKey(e.target.value as 'civic' | 'rav4')}>
            <option value="civic">2021 Honda Civic · HC-2021-001</option>
            <option value="rav4">2022 Toyota RAV4 · TR-2022-002</option>
          </select>
        </label>
        <div className="vehicleLine"><strong>{vehicle.year} {vehicle.make} {vehicle.model}</strong><span>{vehicle.vehicle_id}</span></div>
        <label>Mileage<input type="number" value={mileage} onChange={e => setMileage(Number(e.target.value))} /></label>
        <label>Customer complaint<textarea rows={5} value={complaint} onChange={e => setComplaint(e.target.value)} /></label>
        <label>Service advisor notes<textarea rows={3} value={notes} onChange={e => setNotes(e.target.value)} /></label>
        <button disabled={loading}>{loading ? 'Investigating…' : 'Investigate'}</button>
        {message && <p className="message">{message}</p>}
      </form>

      <section className="card result">
        <h2>Agent Investigation</h2>
        {!result && <div className="empty">Submit a service concern to start the LangGraph investigation workflow.</div>}
        {result && <>
          <div className={`risk ${result.risk_level}`}>{result.risk_level.replace('_', ' ')}</div>
          <h3>Parsed concern</h3>
          <p><strong>Component:</strong> {result.component}</p>
          <div className="chips">{result.parsed_symptoms.map(s => <span key={s}>{s}</span>)}</div>
          <h3>Tools used</h3>
          <div className="timeline">{result.tools_used.map(t => <div key={t}>✓ {t}</div>)}</div>

          <h3>Evidence summary</h3><p>{result.evidence_summary}</p>
          {result.evidence.length > 0 && <>
            <h3>Evidence citations <small>{result.evidence.length}</small></h3>
            <div className="evidence citations">
              {result.evidence.slice(0, 8).map((item, i) =>
                <div className="citation" key={`${String(item.source_id)}-${i}`}>
                  <strong>{String(item.source_id)}</strong>
                  <span>{String(item.title || item.source_type)}</span>
                  <p>{String(item.snippet || '')}</p>
                </div>
              )}
            </div>
          </>}
          {result.tool_errors.length > 0 && <p className="message">One or more evidence tools failed. Human review is required.</p>}
          <Evidence title="Matched recalls" items={result.matched_recalls} />
          <Evidence title="Manufacturer technical communications" items={result.matched_tsb} />
          <Evidence title="Prior service context" items={result.prior_service_context} />

          <h3>Recommended inspection steps</h3>
          <ol>{result.recommended_inspection_steps.map(s => <li key={s}>{s}</li>)}</ol>

          <h3>Draft work order</h3>
          <textarea className="workOrder" rows={12} value={workOrder} onChange={e => setWorkOrder(e.target.value)} />
          <div className="approval">
            <span>{result.human_review_required ? 'Human review required' : 'Ready for advisor review'}</span>
            <button type="button" onClick={approve}>Approve work order</button>
          </div>
        </>}
      </section>
    </section>
  </main>
}

function Evidence({ title, items }: { title: string, items: Array<Record<string, unknown>> }) {
  return <div className="evidence"><h3>{title} <small>{items.length}</small></h3>
    {items.length === 0 ? <p className="muted">No matching evidence returned.</p> : items.slice(0, 5).map((item, i) =>
      <details key={i}><summary>{String(item.document_id || item.campaign_number || item.service_date || `Evidence ${i + 1}`)}</summary>
        <pre>{JSON.stringify(item, null, 2)}</pre></details>
    )}
  </div>
}

export default App
