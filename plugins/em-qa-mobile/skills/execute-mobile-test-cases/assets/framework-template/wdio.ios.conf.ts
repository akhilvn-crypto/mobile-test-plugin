import { clean, shared } from './wdio.shared.conf';
import { env, flutterMode } from './utils/env';

/**
 * iPhone (real device, macOS with Xcode only). A real iPhone needs a RELEASE test build with appium_flutter_server
 * for FLUTTER_MODE=integration, and WebDriverAgent signing (IOS_XCODE_ORG_ID / IOS_XCODE_SIGNING_ID).
 * FLUTTER_MODE=native uses XCUITest alone and reaches Flutter only through Semantics labels and identifiers.
 */
process.env.PLATFORM = 'ios';
const integration = flutterMode() === 'integration';

export const config: WebdriverIO.Config = {
  ...shared,
  capabilities: [clean({
    platformName: 'iOS',
    'appium:automationName': integration ? 'FlutterIntegration' : 'XCUITest',
    'appium:udid': env('DEVICE_UDID'),
    'appium:app': env('APP_PATH'),
    'appium:bundleId': env('APP_ID'),
    'appium:noReset': true,
    'appium:newCommandTimeout': 600,
    'appium:xcodeOrgId': env('IOS_XCODE_ORG_ID'),
    'appium:xcodeSigningId': env('IOS_XCODE_SIGNING_ID'),
    'appium:updatedWDABundleId': env('IOS_UPDATED_WDA_BUNDLE_ID'),
    'appium:wdaLaunchTimeout': 180000,
    ...(integration ? {
      'appium:flutterServerLaunchTimeout': 60000,
      'appium:flutterElementWaitTimeout': 1500,
      'appium:flutterScrollMaxIteration': 20,
    } : {}),
  })],
};
