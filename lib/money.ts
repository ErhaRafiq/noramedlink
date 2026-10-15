/** "PKR 1,500" from whole units (the backend stores whole PKR). */
export function formatMoney(amount: number, currency = "pkr") {
  return `${currency.toUpperCase()} ${amount.toLocaleString("en-PK")}`;
}
