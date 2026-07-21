import { useState } from "react";
import { useT } from "../i18n";
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
  const t = useT();
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
        {t("calc.mortgageTitle")}
      </h3>
      <div className="rounded-xl panel p-4 space-y-3">
        <div className="flex flex-wrap gap-4">
          <Field label={t("calc.downPayment")} suffix="%" value={downPct}
            onChange={setDownPct} width="w-20" />
          <Field label={t("calc.interestRate")} suffix={t("calc.perYear")} value={rate}
            onChange={setRate} step={0.1} width="w-20" />
          <Field label={t("calc.duration")} suffix={t("calc.years")} value={years}
            onChange={setYears} width="w-20" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <Stat label={t("calc.loanAmount")} value={formatPrice(loan)} />
          <Stat label={t("calc.downPayment")} value={formatPrice(price - loan)} />
          <Stat label={t("calc.monthlyPayment")} value={formatPrice(mortgage, "rent")} />
        </div>
      </div>

      <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
        {t("calc.yieldTitle")}
      </h3>
      <div className="rounded-xl panel p-4 space-y-3">
        <div className="flex flex-wrap gap-4">
          <Field label={t("calc.expectedRent")} suffix={t("calc.perMonthUnit")} value={rent}
            onChange={setRent} step={50} />
          <Field label={t("calc.costsVacancy")} suffix={t("calc.percentOfRent")} value={costsPct}
            onChange={setCostsPct} width="w-20" />
        </div>
        {grossYield !== null ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <Stat label={t("calc.grossYield")} value={`${grossYield.toFixed(2)}%`} />
            <Stat label={t("calc.netYield")} value={`${(netYield ?? 0).toFixed(2)}%`} />
            <Stat
              label={t("calc.cashFlow")}
              value={formatPrice(cashFlow ?? 0, "rent")}
              accent={(cashFlow ?? 0) >= 0 ? "good" : "bad"}
            />
          </div>
        ) : (
          <p className="text-xs t-dim">{t("calc.enterRent")}</p>
        )}
      </div>
    </>
  );
}
