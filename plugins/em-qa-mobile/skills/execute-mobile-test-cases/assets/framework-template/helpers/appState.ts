import { appId, env, flutterMode, platform } from '../utils/env';

/**
 * App state per case. Every case declares the state it needs and starts from it, so no case depends on another:
 *   fresh install - app data cleared (Android) or app reinstalled (iOS, needs APP_PATH), permissions reset
 *   logged out    - app data cleared, app opened, nobody signed in
 *   logged in     - logged out + signed in as the role (fixtures/auth.ts)
 */
export type AppState = 'fresh install' | 'logged out' | 'logged in';

function id(): string {
  const a = appId();
  if (!a) throw new Error('APP_ID is not set in .env (package name or bundle id of the app under test)');
  return a;
}

/** Opens (or re-opens) the app. On the Flutter layer this also reconnects to the app's test server. */
export async function launch(): Promise<void> {
  if (flutterMode() === 'integration') {
    await driver.execute('flutter: launchApp', { appId: id() });
    return;
  }
  await driver.execute('mobile: activateApp', platform() === 'ios' ? { bundleId: id() } : { appId: id() });
}

export async function terminate(): Promise<void> {
  await driver.execute('mobile: terminateApp', platform() === 'ios' ? { bundleId: id() } : { appId: id() });
}

/** Clears app data (Android: like a new install, runtime permissions reset). iOS: reinstall from APP_PATH. */
export async function clearData(): Promise<void> {
  if (platform() === 'android') {
    await terminate().catch(() => undefined);
    await driver.execute('mobile: clearApp', { appId: id() });
    return;
  }
  const appPath = env('APP_PATH');
  if (!appPath) throw new Error('iOS: a fresh app state needs APP_PATH (the IPA) to reinstall the app');
  await driver.execute('mobile: removeApp', { bundleId: id() }).catch(() => undefined);
  await driver.execute('mobile: installApp', { app: appPath });
}

/** Puts the app in the state the case needs. `signIn` comes from fixtures/auth.ts for 'logged in'. */
export async function startFrom(state: AppState, role?: string, signIn?: (role: string) => Promise<void>): Promise<void> {
  await clearData();
  await launch();
  if (state === 'logged in') {
    if (!role || !signIn) throw new Error("startFrom('logged in') needs the role and the signIn helper");
    await signIn(role);
  }
}

/** Minimises the app (Home) for some seconds and brings it back. seconds = -1 leaves it in the background. */
export async function sendToBackground(seconds = 3): Promise<void> {
  await driver.execute('mobile: backgroundApp', { seconds });
}

/** Closes the app and opens it again (keeps data). */
export async function reopen(): Promise<void> {
  await terminate();
  await launch();
}

/** 0 not installed, 1 not running, 2 background suspended, 3 background, 4 foreground. */
export async function state(): Promise<number> {
  return Number(await driver.queryAppState(id()));
}

export async function isInForeground(): Promise<boolean> {
  return (await state()) === 4;
}

/** Opens a deep link in the app. */
export async function openDeepLink(url: string): Promise<void> {
  if (platform() === 'android') {
    await driver.execute('mobile: deepLink', { url, package: id() });
  } else {
    await driver.execute('mobile: deepLink', { url, bundleId: id() });
  }
}
