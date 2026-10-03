import { appId, platform, waitTimeout } from '../utils/env';
import { findNative } from '../utils/flutter';

/**
 * Permissions. System pop-ups live outside Flutter, so they are handled through native locators.
 * Android button ids belong to the permission controller (Android 10+); labels are a fallback for older versions.
 */
export type Answer = 'allow' | 'while-using' | 'only-this-time' | 'deny' | 'deny-dont-ask';

const ANDROID_BUTTONS: Record<Answer, { ids: string[]; texts: string[] }> = {
  allow: { ids: ['com.android.permissioncontroller:id/permission_allow_button'], texts: ['Allow', 'ALLOW'] },
  'while-using': {
    ids: ['com.android.permissioncontroller:id/permission_allow_foreground_only_button'],
    texts: ['While using the app', 'Allow only while using the app'],
  },
  'only-this-time': { ids: ['com.android.permissioncontroller:id/permission_allow_one_time_button'], texts: ['Only this time'] },
  deny: { ids: ['com.android.permissioncontroller:id/permission_deny_button'], texts: ["Don't allow", 'Deny', 'DENY'] },
  'deny-dont-ask': {
    ids: ['com.android.permissioncontroller:id/permission_deny_and_dont_ask_again_button'],
    texts: ["Don't allow", "Deny & don't ask again", "Don't ask again"],
  },
};

const IOS_BUTTONS: Record<Answer, string[]> = {
  allow: ['Allow', 'OK', 'Allow Full Access'],
  'while-using': ['Allow While Using App', 'Allow'],
  'only-this-time': ['Allow Once'],
  deny: ["Don’t Allow", "Don't Allow"],
  'deny-dont-ask': ["Don’t Allow", "Don't Allow"],
};

/** True when a system permission pop-up is on screen. */
export async function isPermissionDialogShown(timeoutMs = 3000): Promise<boolean> {
  if (platform() === 'android') {
    return !!(await findNative('-android uiautomator',
      'new UiSelector().resourceIdMatches("com\\.(google\\.)?android\\.permissioncontroller:id/.*")', timeoutMs));
  }
  try {
    await driver.waitUntil(async () => !!(await driver.getAlertText().catch(() => '')), { timeout: timeoutMs });
    return true;
  } catch {
    return false;
  }
}

/** Taps the requested answer on the system permission pop-up. Returns the visible message of the pop-up. */
export async function answerPermission(answer: Answer, timeoutMs = waitTimeout()): Promise<string> {
  if (platform() === 'android') {
    const msg = await findNative('id', 'com.android.permissioncontroller:id/permission_message', timeoutMs);
    const text = msg ? await msg.getText() : '';
    const spec = ANDROID_BUTTONS[answer];
    for (const rid of spec.ids) {
      const btn = await findNative('id', rid, 1500);
      if (btn) { await btn.click(); return text; }
    }
    for (const t of spec.texts) {
      const btn = await findNative('-android uiautomator', `new UiSelector().text("${t}")`, 1500);
      if (btn) { await btn.click(); return text; }
    }
    throw new Error(`Permission pop-up: no "${answer}" button found`);
  }
  const text = await driver.getAlertText().catch(() => '');
  for (const label of IOS_BUTTONS[answer]) {
    try {
      await driver.execute('mobile: alert', { action: answer.startsWith('deny') ? 'dismiss' : 'accept', buttonLabel: label });
      return text;
    } catch { /* try the next label */ }
  }
  throw new Error(`Permission alert: no "${answer}" button found`);
}

/** Grants or revokes runtime permissions without the pop-up (Android), e.g. "turn off later in settings". */
export async function setPermissions(action: 'grant' | 'revoke', permissions: string[]): Promise<void> {
  if (platform() !== 'android') throw new Error('Changing permissions from outside the app is only scripted on Android');
  await driver.execute('mobile: changePermissions', { permissions, appPackage: appId(), action });
}

/** Permissions the app currently holds (Android). */
export async function grantedPermissions(): Promise<string[]> {
  if (platform() !== 'android') return [];
  return (await driver.execute('mobile: getPermissions', { type: 'granted', appPackage: appId() })) as unknown as string[];
}
