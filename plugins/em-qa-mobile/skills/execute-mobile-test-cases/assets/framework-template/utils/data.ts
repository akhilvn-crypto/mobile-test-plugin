/** Unique test data, so repeated runs on the same device never collide. */
export function stamp(): string {
  return `${Date.now().toString(36)}${Math.floor(Math.random() * 1296).toString(36)}`;
}

export function uniqueEmail(prefix = 'qa'): string {
  return `${prefix}.${stamp()}@example.com`;
}

export function uniqueName(prefix = 'QA'): string {
  return `${prefix} ${stamp()}`;
}

export function uniquePhone(): string {
  return `9${String(Date.now()).slice(-9)}`;
}
