import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import dotenv from 'dotenv';

/** Root of mobile-automation/ (this file lives in utils/). */
export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

dotenv.config({ path: path.join(ROOT, '.env'), quiet: true } as dotenv.DotenvConfigOptions);

export type Platform = 'android' | 'ios';

export function env(name: string, fallback = ''): string {
  const v = process.env[name];
  return v === undefined || v === '' ? fallback : v;
}

export function platform(): Platform {
  return env('PLATFORM', 'android').toLowerCase() === 'ios' ? 'ios' : 'android';
}

/** integration = Flutter Integration Driver (test build); native = accessibility-tree fallback. */
export function flutterMode(): 'integration' | 'native' {
  return env('FLUTTER_MODE', 'integration').toLowerCase() === 'native' ? 'native' : 'integration';
}

export function waitTimeout(): number {
  return Number(env('WAIT_TIMEOUT_MS', '15000')) || 15000;
}

/** Package name / bundle id of the app under test. */
export function appId(): string {
  return env('APP_ID');
}

interface RoleMap { roles: Record<string, { user: string; password: string }> }

function roleMap(): RoleMap {
  const p = path.join(ROOT, 'test-data', 'credentials.map.json');
  if (!fs.existsSync(p)) return { roles: {} };
  return JSON.parse(fs.readFileSync(p, 'utf8')) as RoleMap;
}

/** Role -> values from .env, through the variable NAMES in test-data/credentials.map.json. */
export function credentials(role: string): { user: string; password: string } {
  const entry = roleMap().roles[role];
  if (!entry) throw new Error(`Role '${role}' is not in test-data/credentials.map.json`);
  const user = env(entry.user);
  const password = env(entry.password);
  if (!user || !password) throw new Error(`Credentials for role '${role}' are not filled in .env`);
  return { user, password };
}

export function configuredRoles(): string[] {
  const roles = roleMap().roles;
  return Object.keys(roles).filter((r) => env(roles[r].user) && env(roles[r].password));
}

/** Every .env value that must never appear in evidence (passwords, tokens, user names). */
export function secretValues(): string[] {
  return Object.entries(process.env)
    .filter(([k, v]) => v && v.length >= 4 && /PASS|SECRET|TOKEN|KEY|PWD|PIN|OTP|_USER$|EMAIL/i.test(k))
    .map(([, v]) => v as string);
}
