import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity, AlertTriangle, ArrowLeft, CheckCircle2, Cpu, EyeOff,
  FileSpreadsheet, Gauge, Lock, ShieldCheck, Sparkles, XCircle,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { api, ApiError } from '../../lib/api'
import {
  ContribBar, Counter, Magnetic, Panel, Pill, Skeleton, Sparkline, useAsync,
} from './Primitives'
import Upload from './Upload'

const ROLE_ICON = { sales_director: Activity, cfo: Gauge, analyst: EyeOff }

const fadeUp = {
  hidden: { opacity: 0, y: 18 },
  show: (i = 0) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.55, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] },
  }),
}

/* ────────────────────────────────────────────────────────── offline notice */
function Offline({ error }) {
  return (
    <div className="mx-auto max-w-lg px-6 py-32 text-center">
      <div className="glass-solid rounded-3xl p-10">
        <XCircle className="mx-auto mb-5 h-10 w-10 text-rose-400" aria-hidden="true" />
        <h2 className="text-2xl font-bold text-white">The engine is not answering</h2>
        <p className="mt-3 text-sm leading-relaxed text-white/55">
          This console shows live output from the FRIDAY engine. It does not
          cache, mock or fabricate anything, so with the API down there is
          nothing honest to display.
        </p>
        <div className="mt-6 rounded-xl bg-black/40 p-4 text-left font-mono text-[11px] leading-relaxed text-cyan">
          cd D:\Accenture\friday<br />
          python -m uvicorn friday.api:app --port 8000
        </div>
        {error && (
          <p className="mt-4 font-mono text-[11px] text-white/30">{String(error.message)}</p>
        )}
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────── gate matrix */
function Gates({ gates }) {
  return (
    <div className="space-y-2">
      {gates.map((g) => (
        <div key={g.driver} className="rounded-xl bg-white/[0.02] p-3 ring-1 ring-white/[0.05]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-white/85">{g.driver}</span>
              <Pill tone={g.kind === 'evidential' ? 'info' : 'neutral'}>{g.kind}</Pill>
            </div>
            <Pill tone={g.status === 'cause' ? 'good' : 'neutral'}>{g.status}</Pill>
          </div>

          <div className="mt-2.5 flex gap-1.5">
            {[
              ['sequence', g.sequence],
              ['magnitude', g.magnitude],
              ['mechanism', g.mechanism],
            ].map(([name, ok]) => (
              <span
                key={name}
                className={`flex-1 rounded-lg px-2 py-1.5 text-center text-[10px] font-medium uppercase tracking-wider ring-1 ${
                  ok
                    ? 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/20'
                    : 'bg-white/[0.03] text-white/30 ring-white/[0.06]'
                }`}
              >
                {name}
              </span>
            ))}
          </div>

          {g.reasons?.length > 0 && (
            <p className="mt-2 text-[11px] leading-relaxed text-white/35">{g.reasons[0]}</p>
          )}
        </div>
      ))}
    </div>
  )
}

/* ─────────────────────────────────────────────────────────── main console */
export default function Console() {
  const [role, setRole] = useState('sales_director')
  const [selected, setSelected] = useState(null)
  const [tab, setTab] = useState('explain')

  const health = useAsync(() => api.health(), [])
  const roles = useAsync(() => api.roles(), [])
  const alerts = useAsync(() => api.alerts(role), [role])

  // Reset the selection when the persona changes: an alert one role can see is
  // frequently one another may not, and holding a stale selection would ask
  // the API for something the new role is forbidden from reading.
  useEffect(() => { setSelected(null) }, [role])

  const active = useMemo(() => {
    if (!alerts.data?.length) return null
    return alerts.data.find((a) => `${a.kpi}|${a.slice}` === selected) ?? alerts.data[0]
  }, [alerts.data, selected])

  const explain = useAsync(
    () =>
      active
        ? api.explain(role, active.kpi, active.filters?.region)
        : Promise.resolve(null),
    [role, active?.kpi, active?.slice]
  )

  const series = useAsync(
    () =>
      active
        ? api.series(active.kpi, active.filters?.region, 90).catch(() => [])
        : Promise.resolve([]),
    [active?.kpi, active?.slice]
  )

  if (health.error) return <Offline error={health.error} />

  const d = explain.data
  const t = d?.telemetry
  const roleMeta = roles.data?.find((r) => r.id === role)

  return (
    <div className="relative z-10 mx-auto max-w-[1400px] px-4 pb-24 pt-28 sm:px-6">
      {/* ── header ───────────────────────────────────────────────────── */}
      <motion.div variants={fadeUp} initial="hidden" animate="show"
                  className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to="/" className="mb-3 inline-flex items-center gap-1.5 text-xs text-white/40 transition-colors hover:text-cyan">
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Back to overview
          </Link>
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Engine <span className="text-gradient">console</span>
          </h1>
          <p className="mt-1.5 text-sm text-white/45">
            Live output from the running engine. Nothing on this page is cached or mocked.
          </p>
        </div>

        {health.data && (
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="good"><CheckCircle2 className="h-3 w-3" /> engine online</Pill>
            <Pill tone="neutral">{health.data.kpis} KPIs</Pill>
            <Pill tone="neutral">{health.data.sources} sources</Pill>
            <Pill tone="neutral">{health.data.period}</Pill>
          </div>
        )}
      </motion.div>

      {/* ── persona switch ───────────────────────────────────────────── */}
      <motion.div variants={fadeUp} initial="hidden" animate="show" custom={1}
                  className="mb-6 grid gap-3 sm:grid-cols-3">
        {(roles.data ?? []).map((r, i) => {
          const Icon = ROLE_ICON[r.id] ?? Sparkles
          const on = r.id === role
          return (
            <button
              key={r.id}
              onClick={() => setRole(r.id)}
              aria-pressed={on}
              className={`group relative overflow-hidden rounded-2xl border p-4 text-left transition-all duration-300 ${
                on
                  ? 'border-violet/50 bg-violet/[0.08] neon-violet'
                  : 'border-white/[0.07] bg-white/[0.02] hover:border-white/20'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <span className={`grid h-9 w-9 place-items-center rounded-xl ${on ? 'bg-violet/25' : 'bg-white/5'}`}>
                  <Icon className={`h-4 w-4 ${on ? 'text-cyan' : 'text-white/45'}`} aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className={`truncate text-sm font-medium ${on ? 'text-white' : 'text-white/70'}`}>{r.label}</p>
                  <p className="truncate text-[11px] text-white/35">
                    {r.visibleKpis}/{r.totalKpis} KPIs · {r.scope}
                  </p>
                </div>
              </div>
              <div className="mt-2.5 flex flex-wrap gap-1">
                {r.masksAccounts && <Pill tone="warn"><Lock className="h-2.5 w-2.5" /> masked</Pill>}
                {r.decisionRights.length === 0
                  ? <Pill tone="neutral">no decision rights</Pill>
                  : <Pill tone="info">{r.decisionRights.length} rights</Pill>}
              </div>
            </button>
          )
        })}
      </motion.div>

      {/* ── bento grid ───────────────────────────────────────────────── */}
      <div className="grid gap-3 lg:grid-cols-12">
        {/* alerts rail */}
        <motion.div variants={fadeUp} initial="hidden" animate="show" custom={2}
                    className="lg:col-span-3">
          <Panel className="h-full p-4" spotlight={false}>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-white/45">
                Material movements
              </h2>
              <Pill tone="info">{alerts.data?.length ?? 0}</Pill>
            </div>

            {alerts.loading && <div className="space-y-2">{[0,1,2].map(i => <Skeleton key={i} className="h-14" />)}</div>}

            <div className="space-y-1.5">
              {(alerts.data ?? []).map((a) => {
                const key = `${a.kpi}|${a.slice}`
                const on = active && `${active.kpi}|${active.slice}` === key
                return (
                  <button
                    key={key}
                    onClick={() => setSelected(key)}
                    className={`w-full rounded-xl px-3 py-2.5 text-left transition-all duration-200 ${
                      on ? 'bg-violet/15 ring-1 ring-violet/40' : 'hover:bg-white/[0.04]'
                    }`}
                  >
                    <p className={`truncate text-sm ${on ? 'text-white' : 'text-white/70'}`}>{a.label}</p>
                    <div className="mt-1 flex items-center justify-between gap-2">
                      <span className="truncate text-[11px] text-white/35">{a.slice}</span>
                      <span className={`shrink-0 font-mono text-xs font-semibold ${a.pct < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                        {a.pct > 0 ? '+' : ''}{a.pct}%
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>

            <p className="mt-4 border-t border-white/[0.06] pt-3 text-[11px] leading-relaxed text-white/30">
              Movements inside a KPI's own normal range never appear here. Silence
              is the feature.
            </p>
          </Panel>
        </motion.div>

        {/* headline + narrative */}
        <motion.div variants={fadeUp} initial="hidden" animate="show" custom={3}
                    className="lg:col-span-6">
          <Panel className="h-full p-5">
            {explain.loading && <div className="space-y-3"><Skeleton className="h-8 w-2/3" /><Skeleton className="h-24" /></div>}

            {explain.error && explain.error instanceof ApiError && explain.error.status === 403 && (
              <div className="rounded-xl bg-amber-400/[0.07] p-4 ring-1 ring-amber-400/20">
                <div className="mb-1.5 flex items-center gap-2">
                  <Lock className="h-4 w-4 text-amber-300" aria-hidden="true" />
                  <span className="text-sm font-medium text-amber-200">Access refused</span>
                </div>
                <p className="text-[13px] leading-relaxed text-white/55">{explain.error.message}</p>
                <p className="mt-2 text-[11px] text-white/35">
                  This is the entitlement layer working, not an error.
                </p>
              </div>
            )}

            {d && (
              <>
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <Pill tone={d.abstained ? 'warn' : 'good'}>
                    confidence: {d.confidence}
                  </Pill>
                  {d.abstained && <Pill tone="warn"><AlertTriangle className="h-3 w-3" /> abstained</Pill>}
                  {d.masked && <Pill tone="info"><Lock className="h-3 w-3" /> names masked</Pill>}
                  <Pill tone="neutral">{d.persona}</Pill>
                </div>

                <h2 className="text-xl font-semibold leading-snug tracking-tight text-white">
                  {d.headline}
                </h2>

                {/* causal chain */}
                {d.chain?.rootCause && (
                  <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl bg-white/[0.03] p-3 ring-1 ring-white/[0.06]">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/35">chain</span>
                    {[
                      d.chain.rootCause,
                      `${d.chain.lever} (${Math.round((d.chain.leverShare ?? 0) * 100)}%)`,
                      `${d.movement.label} ${d.movement.pct}%`,
                    ].map((node, i) => (
                      <span key={i} className="flex items-center gap-2">
                        {i > 0 && <span className="text-violet">›</span>}
                        <span className="rounded-lg bg-black/30 px-2.5 py-1 font-mono text-[11px] text-white/80">{node}</span>
                      </span>
                    ))}
                  </div>
                )}

                <p className="mt-4 text-[15px] leading-relaxed text-white/65">{d.narrative}</p>

                {d.guardViolations?.length > 0 && (
                  <div className="mt-4 rounded-xl bg-rose-500/[0.08] p-3.5 ring-1 ring-rose-400/25">
                    <div className="mb-1 flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-rose-300" aria-hidden="true" />
                      <span className="text-sm font-medium text-rose-200">Numeric guard fired</span>
                    </div>
                    <p className="text-[13px] leading-relaxed text-white/60">
                      The model wrote {d.guardViolations.join(', ')}, which no stage
                      computed. The generated text was discarded.
                    </p>
                  </div>
                )}

                {d.abstained && (
                  <div className="mt-4 rounded-xl bg-amber-400/[0.06] p-3.5 ring-1 ring-amber-400/20">
                    <p className="text-[13px] font-medium text-amber-200">No cause asserted</p>
                    <p className="mt-1 text-[12px] leading-relaxed text-white/50">
                      {d.abstainReasons?.join('; ')}
                    </p>
                    {d.nextCheck && (
                      <p className="mt-2 text-[12px] leading-relaxed text-cyan/80">→ {d.nextCheck}</p>
                    )}
                  </div>
                )}
              </>
            )}
          </Panel>
        </motion.div>

        {/* metrics stack */}
        <motion.div variants={fadeUp} initial="hidden" animate="show" custom={4}
                    className="grid gap-3 lg:col-span-3">
          {d && (
            <>
              <Panel className="p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/40">Current</p>
                <p className="mt-1 font-mono text-2xl font-semibold text-white">
                  <Counter value={d.movement.current} decimals={d.movement.current < 1000 ? 2 : 0} />
                </p>
                <p className={`mt-1 font-mono text-sm ${d.movement.pct < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {d.movement.pct > 0 ? '+' : ''}{d.movement.pct}% vs prior
                </p>
                <div className="mt-3">
                  <Sparkline points={series.data ?? []} />
                </div>
              </Panel>

              <Panel className="p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/40">Signal strength</p>
                <p className="mt-1 font-mono text-2xl font-semibold text-cyan">
                  <Counter value={d.movement.z ?? 0} decimals={2} suffix="σ" />
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-white/35">
                  against a normal swing of {d.movement.normalSwing ?? '—'}%
                </p>
              </Panel>

              {t && (
                <Panel className="p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/40">Cost of this answer</p>
                  <div className="mt-2 grid grid-cols-2 gap-2 font-mono text-sm">
                    <div>
                      <p className="text-white"><Counter value={t.totalMs} decimals={0} suffix=" ms" /></p>
                      <p className="text-[10px] text-white/35">latency</p>
                    </div>
                    <div>
                      <p className="text-white">₹<Counter value={t.costInr} decimals={3} /></p>
                      <p className="text-[10px] text-white/35">estimated</p>
                    </div>
                    <div>
                      <p className="text-white"><Counter value={t.modelCalls} /></p>
                      <p className="text-[10px] text-white/35">model calls</p>
                    </div>
                    <div>
                      <p className="text-white"><Counter value={t.tokens} /></p>
                      <p className="text-[10px] text-white/35">tokens</p>
                    </div>
                  </div>
                  {t.violations?.length === 0 && (
                    <p className="mt-3 flex items-start gap-1.5 text-[10px] leading-relaxed text-emerald-300/70">
                      <Cpu className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                      no deterministic stage issued a model call
                    </p>
                  )}
                </Panel>
              )}
            </>
          )}
        </motion.div>

        {/* tabs: attribution / gates / evidence / actions */}
        <motion.div variants={fadeUp} initial="hidden" animate="show" custom={5}
                    className="lg:col-span-8">
          <Panel className="h-full p-5" spotlight={false}>
            <div className="mb-4 flex flex-wrap gap-1 border-b border-white/[0.06] pb-2">
              {[
                ['explain', 'Attribution'],
                ['gates', 'Causal gates'],
                ['evidence', 'Evidence'],
                ['actions', 'Actions'],
                ['method', 'Method'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={`relative rounded-lg px-3.5 py-2 text-[13px] transition-colors ${
                    tab === id ? 'text-white' : 'text-white/45 hover:text-white/75'
                  }`}
                >
                  {label}
                  {tab === id && (
                    <motion.span layoutId="console-tab"
                      className="absolute inset-x-1 -bottom-2 h-0.5 rounded-full bg-gradient-to-r from-violet to-cyan" />
                  )}
                </button>
              ))}
            </div>

            <AnimatePresence mode="wait">
              <motion.div key={tab}
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}>

                {tab === 'explain' && d && (
                  <>
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="text-sm font-medium text-white/80">Price, volume and mix</h3>
                      <Pill tone={d.reconciled ? 'good' : 'bad'}>
                        residual {Math.abs(d.residual ?? 0).toExponential(1)}
                      </Pill>
                    </div>
                    {d.contributions.map((c) => (
                      <ContribBar key={c.effect} label={c.effect} value={c.value}
                                  share={c.share_of_movement} unit={d.movement.unit} />
                    ))}
                    {d.byAccount?.length > 0 && (
                      <>
                        <h3 className="mb-1 mt-5 text-sm font-medium text-white/80">Largest contributors</h3>
                        {d.byAccount.slice(0, 4).map((c) => (
                          <ContribBar key={c.effect} label={c.effect} value={c.value}
                                      share={c.share_of_movement} unit={d.movement.unit} />
                        ))}
                      </>
                    )}
                  </>
                )}

                {tab === 'gates' && d && <Gates gates={d.gates} />}

                {tab === 'evidence' && d && (
                  <div className="space-y-2.5">
                    {d.evidence.length === 0 && (
                      <p className="text-sm text-white/35">No supporting passages for this slice.</p>
                    )}
                    {d.evidence.map((e, i) => (
                      <div key={i} className="rounded-xl bg-white/[0.02] p-3.5 ring-1 ring-white/[0.05]">
                        <p className="text-[13px] leading-relaxed text-white/70">“{e.text}”</p>
                        <p className="mt-2 font-mono text-[10px] text-white/30">
                          {e.source} · {e.date} · {e.kind} · relevance {e.score} · {e.ageDays}d old
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {tab === 'actions' && d && (
                  <div className="space-y-3">
                    {d.actions.length === 0 && (
                      <p className="text-sm leading-relaxed text-white/45">
                        No actions for this role — it holds no decision rights, so
                        recommending one would be meaningless.
                      </p>
                    )}
                    {d.actions.map((a, i) => (
                      <div key={i} className="rounded-xl bg-white/[0.02] p-4 ring-1 ring-white/[0.05]">
                        <p className="text-sm font-medium text-white">{a.action}</p>
                        <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
                          {[
                            ['driver', a.driver], ['lever', a.controllable_lever],
                            ['owner', a.owner], ['confidence', a.confidence],
                          ].map(([k, v]) => (
                            <div key={k} className="flex gap-2">
                              <span className="w-20 shrink-0 uppercase tracking-wider text-white/30">{k}</span>
                              <span className="text-white/65">{v}</span>
                            </div>
                          ))}
                        </div>
                        <p className="mt-2.5 border-t border-white/[0.05] pt-2.5 text-[11px] leading-relaxed text-white/40">
                          {a.monitoring_plan}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {tab === 'method' && t && (
                  <div className="space-y-2">
                    {t.stages.map((s) => (
                      <div key={s.name}
                           className={`flex items-center gap-3 rounded-xl p-3 ring-1 ${
                             s.method === 'llm'
                               ? 'bg-violet/[0.08] ring-violet/25'
                               : 'bg-white/[0.02] ring-white/[0.05]'
                           }`}>
                        <span className="w-40 shrink-0 truncate font-mono text-[12px] text-white/75">{s.name}</span>
                        <Pill tone={s.method === 'llm' ? 'info' : 'neutral'}>{s.method}</Pill>
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min((s.ms / Math.max(t.totalMs, 1)) * 100, 100)}%` }}
                            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                            className={`h-full rounded-full ${s.method === 'llm' ? 'bg-violet' : 'bg-cyan/60'}`}
                          />
                        </div>
                        <span className="w-16 shrink-0 text-right font-mono text-[11px] text-white/45">
                          {s.ms} ms
                        </span>
                      </div>
                    ))}
                    <p className="pt-2 text-[11px] leading-relaxed text-white/35">
                      Method is declared per stage and checked at runtime. A stage
                      marked deterministic that issued a model call would fail the run.
                    </p>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </Panel>
        </motion.div>

        {/* fact pack */}
        <motion.div variants={fadeUp} initial="hidden" animate="show" custom={6}
                    className="lg:col-span-4">
          <Panel className="h-full p-5" spotlight={false}>
            <h3 className="mb-1 text-sm font-medium text-white/80">The fact pack</h3>
            <p className="mb-3 text-[11px] leading-relaxed text-white/35">
              Every number the narrative was permitted to use, and the stage that
              produced it. Nothing here came from a model.
            </p>
            <div className="max-h-[380px] space-y-1.5 overflow-y-auto pr-1">
              {(d?.factPack ?? []).map((f, i) => (
                <div key={i} className="rounded-lg bg-white/[0.02] px-3 py-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-mono text-[11px] text-cyan">{f.fact}</span>
                    <span className="truncate font-mono text-[11px] text-white/70">{f.value}</span>
                  </div>
                  <p className="mt-0.5 truncate text-[10px] text-white/25">{f.produced_by}</p>
                </div>
              ))}
            </div>
          </Panel>
        </motion.div>

        {/* bring your own data */}
        <motion.div variants={fadeUp} initial="hidden" animate="show" custom={7}
                    className="lg:col-span-12">
          <Upload />
        </motion.div>
      </div>
    </div>
  )
}
