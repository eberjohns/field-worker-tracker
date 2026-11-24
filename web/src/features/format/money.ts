/**
 * Money on screen: one formatter for every amount (v1.16.0). Amounts are shown with the
 * currency of their payroll run or their country (company setting `currency`: AED for AE,
 * SAR for SA), never "$".
 */

export const COUNTRY_CURRENCY: Readonly<Record<string, string>> = { AE: "AED", SA: "SAR" };

/** "AED" for AE, "SAR" for SA; AED when the country is unknown. */
export function currencyForCountry(country: string | null | undefined): string {
  return COUNTRY_CURRENCY[(country ?? "").trim().toUpperCase()] ?? "AED";
}

const toNumber = (v: number | string | null | undefined): number | null => {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
};

/** "1,234.56" (two decimals) or "–". */
export function formatAmount(v: number | string | null | undefined): string {
  const n = toNumber(v);
  return n === null
    ? "–"
    : n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** "AED 1,234.56", "AED -12.00", or "–" when there is no amount. */
export function formatMoney(
  v: number | string | null | undefined,
  currency: string | null | undefined,
): string {
  const amount = formatAmount(v);
  return amount === "–" ? amount : `${currency || "AED"} ${amount}`;
}
