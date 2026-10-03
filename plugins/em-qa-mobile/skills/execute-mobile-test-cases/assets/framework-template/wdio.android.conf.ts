import { clean, shared } from './wdio.shared.conf';
import { env, flutterMode } from './utils/env';

/**
 * Android on a real phone. FLUTTER_MODE=integration uses the Flutter Integration Driver (the build contains
 * appium_flutter_server; native locators still work through it). FLUTTER_MODE=native uses UiAutomator2 alone and
 * reaches Flutter only through Semantics labels and identifiers.
 */
process.env.PLATFORM = 'android';
const integration = flutterMode() === 'integration';

export const config: WebdriverIO.Config = {
  ...shared,
  capabilities: [clean({
    platformName: 'Android',
    'appium:automationName': integration ? 'FlutterIntegration' : 'UiAutomator2',
    'appium:udid': env('DEVICE_UDID'),
    'appium:app': env('APP_PATH'),
    'appium:appPackage': env('APP_ID'),
    'appium:appActivity': env('ANDROID_APP_ACTIVITY'),
    'appium:noReset': true,
    'appium:autoGrantPermissions': false,
    'appium:newCommandTimeout': 600,
    'appium:uiautomator2ServerLaunchTimeout': 120000,
    'appium:adbExecTimeout': 60000,
    ...(integration ? {
      'appium:flutterServerLaunchTimeout': 60000,
      'appium:flutterElementWaitTimeout': 1500,
      'appium:flutterScrollMaxIteration': 20,
    } : {}),
  })],
};
