/**
 * Opens a test session on the connected real device and checks whether the Flutter layer can be reached.
 *   npx tsx tools/session-check.ts [--platform android|ios] [--mode integration|native|auto]
 * Prints one JSON line: {ok, platform, mode, flutterLayer, nativeLayer, device, app, reason}
 * mode auto (default): try the Flutter Integration Driver first; when the build has no appium_flutter_server,
 * try the native driver and report flutterLayer=false (the skill then continues with the native fallback).
 * Exit 0 when any session could be opened, 1 otherwise. Uses the same .env as the suite; prints no secrets.
 */
import { remote } from 'webdriverio';
import { env } from '../utils/env';

const args = process.argv.slice(2);
const arg = (name: string, def: string) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
};
const platform = arg('platform', env('PLATFORM', 'android')).toLowerCase() === 'ios' ? 'ios' : 'android';
const mode = arg('mode', 'auto');
const appium = new URL(env('APPIUM_URL', 'http://127.0.0.1:4723'));

function caps(integration: boolean): Record<string, unknown> {
  const c: Record<string, unknown> = platform === 'android' ? {
    platformName: 'Android',
    'appium:automationName': integration ? 'FlutterIntegration' : 'UiAutomator2',
    'appium:appPackage': env('APP_ID'),
    'appium:appActivity': env('ANDROID_APP_ACTIVITY'),
    'appium:uiautomator2ServerLaunchTimeout': 120000,
  } : {
    platformName: 'iOS',
    'appium:automationName': integration ? 'FlutterIntegration' : 'XCUITest',
    'appium:bundleId': env('APP_ID'),
    'appium:xcodeOrgId': env('IOS_XCODE_ORG_ID'),
    'appium:xcodeSigningId': env('IOS_XCODE_SIGNING_ID'),
    'appium:updatedWDABundleId': env('IOS_UPDATED_WDA_BUNDLE_ID'),
  };
  Object.assign(c, {
    'appium:udid': env('DEVICE_UDID'),
    'appium:app': env('APP_PATH'),
    'appium:noReset': true,
    'appium:newCommandTimeout': 120,
  });
  if (integration) c['appium:flutterServerLaunchTimeout'] = 60000;
  return Object.fromEntries(Object.entries(c).filter(([, v]) => v !== undefined && v !== ''));
}

async function open(integration: boolean) {
  return remote({
    protocol: appium.protocol.replace(':', '') as 'http' | 'https',
    hostname: appium.hostname,
    port: Number(appium.port || 4723),
    path: appium.pathname || '/',
    logLevel: 'silent',
    connectionRetryCount: 0,
    connectionRetryTimeout: 300000,
    capabilities: caps(integration) as WebdriverIO.Capabilities,
  });
}

async function describeDevice(b: WebdriverIO.Browser) {
  let info: Record<string, unknown> = {};
  try {
    info = (await b.execute('mobile: deviceInfo')) as unknown as Record<string, unknown>;
  } catch { /* optional */ }
  return { model: info.model ?? info.name ?? '', manufacturer: info.manufacturer ?? '', osVersion: info.platformVersion ?? '' };
}

function firstLine(e: unknown): string {
  return String((e as Error)?.message ?? e).split('\n')[0].slice(0, 300);
}

async function main() {
  const out: Record<string, unknown> = { ok: false, platform, mode, flutterLayer: false, nativeLayer: false };
  if (mode !== 'native') {
    try {
      const b = await open(true);
      out.flutterLayer = true;
      out.nativeLayer = true;
      out.mode = 'integration';
      out.device = await describeDevice(b);
      await b.deleteSession();
      out.ok = true;
    } catch (e) {
      out.flutterReason = firstLine(e);
    }
  }
  if (!out.ok && mode !== 'integration') {
    try {
      const b = await open(false);
      out.nativeLayer = true;
      out.mode = 'native';
      out.device = await describeDevice(b);
      await b.deleteSession();
      out.ok = true;
    } catch (e) {
      out.nativeReason = firstLine(e);
    }
  }
  if (!out.ok) out.reason = String(out.nativeReason ?? out.flutterReason ?? 'no session could be opened');
  else if (!out.flutterLayer && mode === 'auto') {
    out.reason = 'The Flutter layer could not be reached (the build may not contain appium_flutter_server); '
      + 'the native fallback works.';
  }
  console.log(JSON.stringify(out));
  process.exit(out.ok ? 0 : 1);
}

main();
