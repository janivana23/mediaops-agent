import {
  IconChevronRight,
  IconClock,
  IconCoins,
  IconRefresh,
  IconScale,
  IconShieldCheck,
  IconSparkles,
} from './icons'
import { SectionHeading } from './SectionHeading'

const STEPS = [
  {
    n: 1,
    icon: <IconCoins />,
    title: 'Budget check',
    body: 'Refuses outright if even the cheapest resolution would blow the client’s remaining monthly budget — spend is summed fresh from an append-only ledger every time, never a mutable counter that could drift.',
  },
  {
    n: 2,
    icon: <IconClock />,
    title: 'Approval checkpoint',
    body: 'Jobs above a cost threshold never auto-generate, no matter how much budget is left. They stop and wait for a human to approve or reject — evaluated against a stable reference price, decided before any provider runs.',
  },
  {
    n: 3,
    icon: <IconScale />,
    title: 'Cost-aware resolution',
    body: 'If the requested size doesn’t fit what’s left in the budget but a smaller one does, it generates at the smaller size and says so — instead of failing a job outright over a resolution choice.',
  },
  {
    n: 4,
    icon: <IconRefresh />,
    title: 'Provider failover',
    body: 'Tries a real API call first; if it fails for any reason — no credits, rate limit, timeout — it fails over to a local fallback automatically. The job never dies just because one provider is down.',
  },
  {
    n: 5,
    icon: <IconShieldCheck />,
    title: 'QA gate',
    body: 'Identity-consistency and brand-compliance scores are computed from the actual output pixels, not asserted by the generator. A provider can’t self-report a good result — this is the same gate whether the output is real or mocked.',
  },
]

export function HowItWorks() {
  return (
    <div>
      <section>
        <div className="card intro-card">
          <p>
            Most agent demos show an LLM calling a tool. The harder, more commercially
            relevant problem is what happens <em>around</em> that call: who's paying, is
            this spend allowed, does the output actually look like the reference
            character, and what happens when the primary provider is down. Every job
            that reaches this dashboard passed through all five checks below, in this
            order — enforced once, in the service layer, shared by the REST API, the
            MCP server, and this UI. An agent calling the MCP tool gets exactly the
            same limits as a person using the form below.
          </p>
        </div>
      </section>

      <section>
        <SectionHeading icon={<IconSparkles />} title="The pipeline" subtitle="Enforced once, server-side — every caller gets the same limits" />
        <div className="steps-flow">
          {STEPS.map((step, i) => (
            <div className="step-card" key={step.n}>
              <div className="step-top">
                <div className="step-number">{step.n}</div>
                <span className="step-icon" aria-hidden="true">{step.icon}</span>
              </div>
              <div className="step-title">{step.title}</div>
              <div className="step-body">{step.body}</div>
              {i < STEPS.length - 1 && (
                <div className="step-arrow" aria-hidden="true">
                  <IconChevronRight width={13} height={13} />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <SectionHeading icon={<IconShieldCheck />} title="Why this matters" />
        <div className="grid-2">
          <div className="card why-card">
            <div className="client-name">No mutable balances</div>
            <p>
              A client's spend is <code>sum(ledger where month = this month)</code>,
              recomputed on every check. There's no <code>usage_cents</code> field
              that could silently drift from the audit trail.
            </p>
          </div>
          <div className="card why-card">
            <div className="client-name">Nothing is trusted blindly</div>
            <p>
              The QA gate scores actual output pixels. The approval threshold is
              evaluated before failover runs, against a stable price — not
              whatever the job happened to cost after the fact.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
