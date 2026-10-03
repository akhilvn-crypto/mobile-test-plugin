import path from 'node:path';
import { env, ROOT } from './utils/env';
import { afterCase, beforeCase } from './reporters/results-reporter';

/**
 * Settings shared by wdio.android.conf.ts and wdio.ios.conf.ts.
 * Run a dated suite:   npx wdio run wdio.android.conf.ts --spec "tests/<Suite>_<date>/*.spec.ts"
 * Run one case:        npx wdio run wdio.android.conf.ts --spec "tests/<Suite>_<date>/<flow>.spec.ts" --mochaOpts.grep "TC-UI-NEG-014"
 * One device, one session at a time (maxInstances 1). Failed cases run once more automatically (RETRIES).
 */
const appium = new URL(env('APPIUM_URL', 'http://127.0.0.1:4723'));

export function clean<T extends Record<string, unknown>>(caps: T): T {
  return Object.fromEntries(Object.entries(caps).filter(([, v]) => v !== undefined && v !== '')) as T;
}

export const shared: WebdriverIO.Config = {
  runner: 'local',
  tsConfigPath: path.join(ROOT, 'tsconfig.json'),
  protocol: appium.protocol.replace(':', '') as 'http' | 'https',
  hostname: appium.hostname,
  port: Number(appium.port || 4723),
  path: appium.pathname || '/',
  specs: ['./tests/**/*.spec.ts'],
  maxInstances: 1,
  capabilities: [],
  logLevel: 'warn',
  outputDir: path.join(ROOT, 'test-results', 'wdio-logs'),
  waitforTimeout: Number(env('WAIT_TIMEOUT_MS', '15000')),
  connectionRetryTimeout: 240000,
  connectionRetryCount: 1,
  framework: 'mocha',
  reporters: ['spec'],
  mochaOpts: {
    ui: 'bdd',
    timeout: 600000,
    retries: Number(env('RETRIES', '1')),
  },
  beforeTest: async function (test) {
    await beforeCase(test);
  },
  afterTest: async function (test, _context, result) {
    await afterCase(test, result);
  },
};
