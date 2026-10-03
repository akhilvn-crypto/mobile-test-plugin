import { platform } from './env';

export interface DeviceInfo {
  platform: 'android' | 'ios';
  model: string;
  manufacturer: string;
  osVersion: string;
}

/** Model and OS of the device the session runs on (for the report and the bug Environment section). */
export async function deviceInfo(): Promise<DeviceInfo> {
  const caps = driver.capabilities as Record<string, unknown>;
  let info: Record<string, unknown> = {};
  try {
    info = (await driver.execute('mobile: deviceInfo')) as unknown as Record<string, unknown>;
  } catch {
    /* older drivers: fall back to the session capabilities */
  }
  const p = platform();
  return {
    platform: p,
    model: String(info.model ?? info.name ?? caps['appium:deviceModel'] ?? caps['deviceModel'] ?? ''),
    manufacturer: String(info.manufacturer ?? caps['appium:deviceManufacturer'] ?? (p === 'ios' ? 'Apple' : '')),
    osVersion: String(info.platformVersion ?? caps['appium:platformVersion'] ?? caps['platformVersion'] ?? ''),
  };
}
