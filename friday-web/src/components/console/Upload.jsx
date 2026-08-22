import { useCallback, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Loader2, Upload as UploadIcon } from 'lucide-react'

import { api } from '../../lib/api'
import { ContribBar, Panel, Pill } from './Primitives'

/**
 * Bring your own data.
 *
 * The single most persuasive panel on the page, because it is the only one a
 * sceptic can point at their own file. It runs the same engine endpoints as
 * everything above; the only difference is where the rows came from.
 */
export default function Upload() {
  const [drag, setDrag] = useState(false)
  const [state, setState] = useState({ status: 'idle' }) // idle|busy|done|error
  const input = useRef(null)

  const send = useCallback(async (file) => {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setState({ status: 'error', message: 'That is not a CSV file.' })
      return
    }
    setState({ status: 'busy', name: file.name })
    try {
      const data = await api.analyse(file, 28)
      setState({ status: 'done', data })
    } catch (e) {
      setState({ status: 'error', message: e.message })
    }
  }, [])

  const onDrop = (e) => {
    e.preventDefault()
    setDrag(false)
    send(e.dataTransfer.files?.[0])
  }

  const d = state.data
  const material = d?.findings?.filter((f) => f.material) ?? []

  return (
    <Panel className="p-5" spotlight={false}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-white/85">Bring your own data</h3>
          <p className="mt-0.5 text-[11px] leading-relaxed text-white/35">
            Drop a CSV with a date column and a numeric column. The engine profiles
            it, writes a contract for it, and runs the identical pipeline.
          </p>
        </div>
        <Pill tone="info">same engine, unseen data</Pill>
      </div>

      {/* drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => input.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-all duration-300 ${
          drag
            ? 'border-cyan/60 bg-cyan/[0.06]'
            : 'border-white/10 bg-white/[0.015] hover:border-white/25'
        }`}
      >
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => send(e.target.files?.[0])}
        />

        {state.status === 'busy' ? (
          <>
            <Loader2 className="mx-auto mb-2 h-7 w-7 animate-spin text-cyan" aria-hidden="true" />
            <p className="text-sm text-white/70">Profiling {state.name}…</p>
          </>
        ) : (
          <>
            <UploadIcon className={`mx-auto mb-2 h-7 w-7 ${drag ? 'text-cyan' : 'text-white/35'}`} aria-hidden="true" />
            <p className="text-sm text-white/65">
              Drop a CSV here, or <span className="text-cyan">browse</span>
            </p>
            <p className="mt-1 text-[11px] text-white/30">
              Needs a date column, one numeric column, ideally 84+ days
            </p>
          </>
        )}
      </div>

      <AnimatePresence>
        {state.status === 'error' && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-3 rounded-xl bg-rose-500/[0.08] p-3.5 ring-1 ring-rose-400/25"
          >
            <p className="text-[13px] text-rose-200">{state.message}</p>
            <p className="mt-1 text-[11px] text-white/40">
              Refusing a file it cannot analyse is correct behaviour. Guessing would not be.
            </p>
          </motion.div>
        )}

        {state.status === 'done' && d && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="mt-4 space-y-4"
          >
            {/* profile summary */}
            <div className="grid gap-2 sm:grid-cols-4">
              {[
                ['rows', d.profile.rows?.toLocaleString('en-IN')],
                ['date column', d.profile.dateColumn ?? 'none'],
                ['measures', d.profile.measures?.length],
                ['dimensions', d.profile.dimensions?.length],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl bg-white/[0.03] p-3">
                  <p className="text-[10px] uppercase tracking-wider text-white/35">{k}</p>
                  <p className="mt-0.5 truncate font-mono text-sm text-white">{v}</p>
                </div>
              ))}
            </div>

            <p className="text-[11px] text-white/35">
              <FileSpreadsheet className="mr-1 inline h-3 w-3" aria-hidden="true" />
              {d.filename} · {d.profile.dateMin} to {d.profile.dateMax} ·
              comparing {d.period} against {d.prior}
            </p>

            {d.profile.warnings?.map((w, i) => (
              <p key={i} className="flex items-start gap-2 rounded-lg bg-amber-400/[0.06] p-2.5 text-[11px] leading-relaxed text-amber-200/85">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />{w}
              </p>
            ))}

            {!d.profile.supportsPvm && (
              <p className="rounded-lg bg-white/[0.03] p-2.5 text-[11px] leading-relaxed text-white/45">
                Price, volume and mix is unavailable for this file — it needs a
                unit-count column and a unit-price column. Contribution by segment
                is shown instead.
              </p>
            )}

            {d.errors?.length > 0 && (
              <p className="rounded-lg bg-rose-500/[0.06] p-2.5 text-[11px] text-rose-200/80">
                {d.errors.join(' · ')}
              </p>
            )}

            {/* findings */}
            {material.length === 0 ? (
              <div className="rounded-xl bg-white/[0.03] p-4">
                <p className="flex items-center gap-2 text-sm text-white/75">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" aria-hidden="true" />
                  No material movement found
                </p>
                <p className="mt-1.5 text-[12px] leading-relaxed text-white/45">
                  Every measure stayed inside its own normal range. This is a
                  result, not a failure — a system that always finds something is
                  a system nobody can trust.
                </p>
              </div>
            ) : (
              material.map((f) => (
                <div key={f.kpi} className="rounded-xl bg-white/[0.02] p-4 ring-1 ring-white/[0.05]">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium text-white">{f.label}</span>
                    <div className="flex gap-1.5">
                      <Pill tone={f.pct < 0 ? 'bad' : 'good'}>{f.pct > 0 ? '+' : ''}{f.pct}%</Pill>
                      <Pill tone="neutral">{f.z}σ</Pill>
                      <Pill tone={f.abstained ? 'warn' : 'good'}>{f.confidence}</Pill>
                    </div>
                  </div>

                  {f.narrative && (
                    <p className="mb-3 text-[13px] leading-relaxed text-white/60">{f.narrative}</p>
                  )}

                  {f.contributions?.length > 0 && (
                    <>
                      <p className="mb-1 text-[11px] uppercase tracking-wider text-white/35">
                        by {f.dimension}
                      </p>
                      {f.contributions.slice(0, 5).map((c) => (
                        <ContribBar key={c.effect} label={c.effect} value={c.value}
                                    share={c.share_of_movement} />
                      ))}
                    </>
                  )}

                  {f.abstained && (
                    <p className="mt-2 rounded-lg bg-amber-400/[0.06] p-2.5 text-[11px] leading-relaxed text-amber-200/80">
                      No cause asserted. {f.abstainReasons?.[0]}
                    </p>
                  )}

                  <p className="mt-2 font-mono text-[10px] text-white/25">
                    {f.telemetry.totalMs} ms · {f.telemetry.modelCalls} model calls
                  </p>
                </div>
              ))
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </Panel>
  )
}
