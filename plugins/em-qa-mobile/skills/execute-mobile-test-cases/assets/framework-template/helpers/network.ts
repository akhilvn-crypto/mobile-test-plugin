import { platform } from '../utils/env';

/**
 * Network switch on a real device. Android allows Wi-Fi and mobile data changes on most devices (airplane mode
 * usually needs a rooted device); iOS does not let a script change the network. When a change is not possible the
 * result says why, and the case becomes "Needs manual check: <reason>" (manualCheck in fixtures).
 */
export interface NetworkResult { ok: boolean; reason?: string }

export interface Connectivity { wifi?: boolean; data?: boolean; airplaneMode?: boolean }

export async function getConnectivity(): Promise<Connectivity> {
  if (platform() !== 'android') return {};
  try {
    return (await driver.execute('mobile: getConnectivity', {})) as Connectivity;
  } catch {
    return {};
  }
}

export async function setConnectivity(target: Connectivity): Promise<NetworkResult> {
  if (platform() !== 'android') {
    return { ok: false, reason: 'the network of an iPhone cannot be changed by the test run' };
  }
  try {
    await driver.execute('mobile: setConnectivity', target);
  } catch (e) {
    return { ok: false, reason: `the device did not allow the network change (${String((e as Error).message).split('\n')[0]})` };
  }
  const now = await getConnectivity();
  const wrong = (Object.keys(target) as (keyof Connectivity)[]).filter((k) => k in now && now[k] !== target[k]);
  return wrong.length ? { ok: false, reason: `the device kept ${wrong.join(', ')} unchanged` } : { ok: true };
}

/** No connection at all (Wi-Fi and mobile data off). */
export function goOffline(): Promise<NetworkResult> {
  return setConnectivity({ wifi: false, data: false });
}

export function goOnline(): Promise<NetworkResult> {
  return setConnectivity({ wifi: true, data: true });
}

export function wifiOnly(): Promise<NetworkResult> {
  return setConnectivity({ wifi: true, data: false });
}

export function mobileDataOnly(): Promise<NetworkResult> {
  return setConnectivity({ wifi: false, data: true });
}
