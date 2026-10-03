/** IST (UTC+05:30, no daylight saving) in the formats the test case files use. */
function ist(d = new Date()): Date {
  return new Date(d.getTime() + (5 * 60 + 30) * 60 * 1000);
}

const p2 = (n: number) => String(n).padStart(2, '0');

/** dd-mm-yyyy hh:mm:ss IST */
export function istCell(d = new Date()): string {
  const t = ist(d);
  return `${p2(t.getUTCDate())}-${p2(t.getUTCMonth() + 1)}-${t.getUTCFullYear()} `
    + `${p2(t.getUTCHours())}:${p2(t.getUTCMinutes())}:${p2(t.getUTCSeconds())} IST`;
}

/** YYYY-MM-DD_HH-MM-SS-IST */
export function istFile(d = new Date()): string {
  const t = ist(d);
  return `${t.getUTCFullYear()}-${p2(t.getUTCMonth() + 1)}-${p2(t.getUTCDate())}_`
    + `${p2(t.getUTCHours())}-${p2(t.getUTCMinutes())}-${p2(t.getUTCSeconds())}-IST`;
}

/** dd-mm-yyyy */
export function istDate(d = new Date()): string {
  const t = ist(d);
  return `${p2(t.getUTCDate())}-${p2(t.getUTCMonth() + 1)}-${t.getUTCFullYear()}`;
}
