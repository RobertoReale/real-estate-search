import { useState } from "react";
import { formatPrice } from "../services/api";
import type { Property } from "../types";

/** French amortization: fixed monthly payment on the residual loan. */
function monthlyPayment(loan: number, annualRatePct: number, years: number): number {
  const n = years * 12;
  if (n <= 0 || loan <= 0) return 0;
  const r = annualRatePct / 100 / 12;
  if (r === 0) return loan / n;
  return (loan * r) / (1 - Math.pow(1 + r, -n));
}

function Field({ label, suffix, value, onChange, step = 1, width = "w-24" }: {
  label: string; suffix: string; value: number;
  onChange: (v: number) => void; step?: number; width?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs t-muted">
      {label}
      <span className="flex items-center gap-1">
        <input className={`input ${width}`} type="number" step={step} min={0}
          value={value} onChange={(e) => onChange(Number(e.target.value))} />
        <span className="t-dim">{suffix}</span>
      </span>
    </label>
  );
}

function Stat({ label, value, accent }: {
  label: string; value: string; accent?: "good" | "bad";
}) {
  const color =
    accent === "good" ? "accent-good"
    : accent === "bad" ? "accent-bad"
    : "";
  return (
    <div className="rounded-xl panel p-3">
      <p className="text-[11px] uppercase t-dim">{label}</p>
      <p className={`text-base font-bold mt-0.5 ${color}`}>{value}</p>
    </div>
  );
}

/** Mortgage estimator + rental yield calculator for sale properties.
 *  Pure client-side math: nothing is persisted. */
export default function Calculators({ property: p }: { property: Property }) {
  const price = p.current_min_price ?? 0;
  const [downPct, setDownPct] = useState(20);
  const [rate, setRate] = useState(3.5);
  const [years, setYears] = useState(25);
  const [rent, setRent] = useState(0);
  const [costsPct, setCostsPct] = useState(10);

  if (!price || p.contract !== "sale") return null;

  const loan = price * (1 - downPct / 100);
  const mortgage = monthlyPayment(loan, rate, years);

  const grossYield = rent > 0 ? (rent * 12 / price) * 100 : null;
  const netYield = rent > 0 ? (rent * 12 * (1 - costsPct / 100)) / price * 100 : null;
  const cashFlow = rent > 0 ? rent - mortgage : null;

  return (
    <>
      <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
        🧮 Mortgage estimator
      </h3>
      <div className="rounded-xl panel p-4 space-y-3">
        <div className="flex flex-wrap gap-4">
          <Field label="Down payment" suffix="%" value={downPct}
            onChange={setDownPct} width="w-20" />
          <Field label="Interest rate" suffix="%/yr" value={rate}
            onChange={setRate} step={0.1} width="w-20" />
          <Field label="Duration" suffix="years" value={years}
            onChange={setYears} width="w-20" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <Stat label="Loan amount" value={formatPrice(loan)} />
          <Stat label="Down payment" value={formatPrice(price - loan)} />
          <Stat label="Monthly payment" value={`${formatPrice(mortgage)}/mo`} />
        </div>
      </div>

      <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
        📈 Rental yield (investment)
      </h3>
      <div className="rounded-xl panel p-4 space-y-3">
        <div className="flex flex-wrap gap-4">
          <Field label="Expected rent" suffix="€/mo" value={rent}
            onChange={setRent} step={50} />
          <Field label="Costs & vacancy" suffix="% of rent" value={costsPct}
            onChange={setCostsPct} width="w-20" />
        </div>
        {grossYield !== null ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <Stat label="Gross yield" value={`${grossYield.toFixed(2)}%`} />
            <Stat label="Net yield" value={`${(netYield ?? 0).toFixed(2)}%`} />
            <Stat
              label="Cash flow vs mortgage"
              value={`${formatPrice(cashFlow ?? 0)}/mo`}
              accent={(cashFlow ?? 0) >= 0 ? "good" : "bad"}
            />
          </div>
        ) : (
          <p className="text-xs t-dim">
            Enter the rent you expect to charge to see gross/net yield and
            monthly cash flow (rent minus the mortgage payment above).
          </p>
        )}
      </div>
    </>
  );
}
