import { platform, secretValues } from '../utils/env';

const MASK = '********';
const SECRET_PATTERNS: RegExp[] = [
  /\b(Bearer|Basic)\s+[A-Za-z0-9\-._~+/=]{8,}/gi,
  /\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b/g,
  /\b([\w.-]*(?:password|passwd|pwd|token|secret|otp|api_?key|session|cookie)[\w.-]*)\s*[=:]\s*("?)[^\s",;&]+\2/gi,
];

/** Removes .env values, tokens, cookies and password-like values from device log text. */
export function scrub(line: string): string {
  let out = line;
  for (const v of secretValues()) out = out.split(v).join(MASK);
  out = out.replace(SECRET_PATTERNS[0], (_m, kind: string) => `${kind} ${MASK}`);
  out = out.replace(SECRET_PATTERNS[1], MASK);
  out = out.replace(SECRET_PATTERNS[2], (_m, key: string) => `${key}=${MASK}`);
  return out;
}

/**
 * Device log lines since the previous call (Android logcat / iOS syslog), secrets removed.
 * Appium returns only the lines collected since the last read, so a read at the start of a case drains the buffer.
 */
export async function readDeviceLog(): Promise<string[]> {
  const type = platform() === 'ios' ? 'syslog' : 'logcat';
  const entries = (await driver.getLogs(type)) as Array<{ timestamp?: number; level?: string; message?: string }>;
  return entries.map((e) => scrub(String(e.message ?? ''))).filter(Boolean);
}

/** Lines that show the app crashed or stopped responding (crash evidence for bug reports). */
export function crashLines(lines: string[], appId = ''): string[] {
  const out: string[] = [];
  let inCrash = false;
  for (const l of lines) {
    const start = /FATAL EXCEPTION|ANR in |Fatal signal \d+|E\/flutter|\[ERROR:flutter|Unhandled Exception|has crashed|Terminating app due to uncaught exception/.test(l)
      && (!appId || /FATAL EXCEPTION|E\/flutter|\[ERROR:flutter|Unhandled Exception/.test(l) || l.includes(appId));
    if (start) inCrash = true;
    if (inCrash) {
      out.push(l);
      if (out.length > 60) break;
      if (!/^\s|at |Caused by|#\d+|AndroidRuntime|flutter/.test(l) && !start) inCrash = false;
    }
  }
  return out;
}
