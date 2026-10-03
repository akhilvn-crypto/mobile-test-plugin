import { expect } from '@wdio/globals';
import { flutterMode, platform } from '../utils/env';

const usingFlutterLayer = () => flutterMode() === 'integration';
import { describeLoc, find, isShown, scrollTo, waitGone, type Loc } from '../utils/flutter';

/**
 * Base of every screen object. One class per screen in screens/<Name>Screen.ts, built from
 * Exploration/<plan-key>/<platform>/<flow-key>/screens/<screen>.json. Actions are named like the manual steps.
 */
export abstract class BaseScreen {
  /** A control that proves this screen is shown (title, heading or a unique button). */
  protected abstract readonly anchor: Loc;

  async waitUntilShown(timeoutMs?: number): Promise<this> {
    await find(this.anchor, timeoutMs);
    return this;
  }

  async isOpen(timeoutMs = 2000): Promise<boolean> {
    return isShown(this.anchor, timeoutMs);
  }

  protected find(loc: Loc, timeoutMs?: number): Promise<WebdriverIO.Element> {
    return find(loc, timeoutMs);
  }

  async tap(loc: Loc): Promise<void> {
    await (await find(loc)).click();
  }

  async longPress(loc: Loc): Promise<void> {
    const el = await find(loc);
    if (usingFlutterLayer()) {
      await driver.execute('flutter: longPress', { origin: el });
    } else if (platform() === 'android') {
      await driver.execute('mobile: longClickGesture', { elementId: el.elementId, duration: 1000 });
    } else {
      await driver.execute('mobile: touchAndHold', { elementId: el.elementId, duration: 1.0 });
    }
  }

  /** Clears the field and types the text. */
  async enter(loc: Loc, text: string): Promise<void> {
    const el = await find(loc);
    await el.click().catch(() => undefined);
    await el.clearValue().catch(() => undefined);
    await el.setValue(text);
  }

  async textOf(loc: Loc): Promise<string> {
    const el = await find(loc);
    const t = await el.getText().catch(() => '');
    return t || (await el.getAttribute(platform() === 'ios' ? 'label' : 'content-desc').catch(() => '')) || '';
  }

  isShown(loc: Loc, timeoutMs = 2000): Promise<boolean> {
    return isShown(loc, timeoutMs);
  }

  async expectShown(loc: Loc, timeoutMs?: number): Promise<void> {
    await find(loc, timeoutMs).catch(() => {
      throw new Error(`Expected to see ${describeLoc(loc)}`);
    });
  }

  async expectGone(loc: Loc, timeoutMs?: number): Promise<void> {
    await waitGone(loc, timeoutMs);
  }

  /** The exact message text is visible (snackbar, dialog, inline field message). */
  async expectMessage(text: string, timeoutMs?: number): Promise<void> {
    await this.expectShown({ text, name: `message "${text}"` }, timeoutMs);
  }

  async expectText(loc: Loc, text: string): Promise<void> {
    await expect(await this.textOf(loc)).toBe(text);
  }

  async scrollTo(loc: Loc, direction: 'down' | 'up' = 'down'): Promise<WebdriverIO.Element> {
    return scrollTo(loc, direction);
  }

  /** System back button (Android) / back gesture. */
  async back(): Promise<void> {
    await driver.back();
  }

  async hideKeyboard(): Promise<void> {
    if (await driver.isKeyboardShown().catch(() => false)) await driver.hideKeyboard().catch(() => undefined);
  }

  async isKeyboardShown(): Promise<boolean> {
    return driver.isKeyboardShown().catch(() => false);
  }

  /** Pull to refresh: a swipe down from the upper part of the screen. */
  async pullToRefresh(): Promise<void> {
    const { width, height } = await driver.getWindowSize();
    if (platform() === 'android') {
      await driver.execute('mobile: swipeGesture', {
        left: Math.round(width * 0.2), top: Math.round(height * 0.2), width: Math.round(width * 0.6),
        height: Math.round(height * 0.5), direction: 'down', percent: 0.9,
      });
    } else {
      await driver.execute('mobile: swipe', { direction: 'down' });
    }
  }

  async swipe(direction: 'up' | 'down' | 'left' | 'right'): Promise<void> {
    const { width, height } = await driver.getWindowSize();
    if (platform() === 'android') {
      await driver.execute('mobile: swipeGesture', {
        left: Math.round(width * 0.1), top: Math.round(height * 0.2), width: Math.round(width * 0.8),
        height: Math.round(height * 0.6), direction, percent: 0.75,
      });
    } else {
      await driver.execute('mobile: swipe', { direction });
    }
  }

  /** True when the control is fully inside the visible screen and not covered by the keyboard. */
  async isFullyVisible(loc: Loc): Promise<boolean> {
    const el = await find(loc);
    const r = await el.getElementRect(el.elementId);
    const { width, height } = await driver.getWindowSize();
    return r.x >= 0 && r.y >= 0 && r.x + r.width <= width && r.y + r.height <= height;
  }
}
