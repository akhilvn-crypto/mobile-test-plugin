import { flutterMode, platform, waitTimeout } from './env';

/**
 * A control on a Flutter screen, described the way the exploration stored it. Locator order: Semantics label
 * or identifier, then the Flutter key, then visible text, then widget type or tooltip. Never screen coordinates.
 */
export interface Loc {
  /** Semantics label (accessibility label) */
  label?: string;
  /** Semantics identifier (Android resource-id / iOS accessibility identifier) */
  id?: string;
  /** Flutter Key('...') value - reachable only through the Flutter layer */
  key?: string;
  /** Exact visible text */
  text?: string;
  /** Part of the visible text */
  textContains?: string;
  /** Widget type, e.g. ElevatedButton - last resort */
  type?: string;
  tooltip?: string;
  /** Short name used in error messages */
  name?: string;
}

type Strategy = [using: string, value: string];
const W3C_ID = 'element-6066-11e4-a52e-4f735466cecf';

const q = (s: string) => s.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

export function describeLoc(loc: Loc): string {
  if (loc.name) return loc.name;
  const parts = Object.entries(loc).filter(([k]) => k !== 'name').map(([k, v]) => `${k}="${v}"`);
  return parts.join(', ') || 'control';
}

/** The strategies to try for a control, in the agreed order, for the current mode and platform. */
export function strategies(loc: Loc): Strategy[] {
  const out: Strategy[] = [];
  if (flutterMode() === 'integration') {
    if (loc.label) out.push(['-flutter semantics label', loc.label]);
    if (loc.id) out.push(['accessibility id', loc.id], ['id', loc.id]);
    if (loc.key) out.push(['-flutter key', loc.key]);
    if (loc.text) out.push(['-flutter text', loc.text]);
    if (loc.textContains) out.push(['-flutter text containing', loc.textContains]);
    if (loc.tooltip) out.push(['-flutter tooltip', loc.tooltip]);
    if (loc.type) out.push(['-flutter type', loc.type]);
    if (loc.label) out.push(['accessibility id', loc.label]);
    return out;
  }
  // native fallback: only what Flutter exposes to the accessibility tree (no keys, no widget types)
  if (platform() === 'android') {
    if (loc.label) out.push(['accessibility id', loc.label]);
    if (loc.id) out.push(['id', loc.id]);
    if (loc.text) {
      out.push(['-android uiautomator', `new UiSelector().text("${q(loc.text)}")`],
        ['-android uiautomator', `new UiSelector().description("${q(loc.text)}")`]);
    }
    if (loc.textContains) {
      out.push(['-android uiautomator', `new UiSelector().textContains("${q(loc.textContains)}")`],
        ['-android uiautomator', `new UiSelector().descriptionContains("${q(loc.textContains)}")`]);
    }
    if (loc.tooltip) out.push(['accessibility id', loc.tooltip]);
  } else {
    if (loc.label) out.push(['accessibility id', loc.label]);
    if (loc.id) out.push(['accessibility id', loc.id]);
    if (loc.text) out.push(['-ios predicate string', `label == "${q(loc.text)}" OR value == "${q(loc.text)}"`]);
    if (loc.textContains) {
      out.push(['-ios predicate string',
        `label CONTAINS "${q(loc.textContains)}" OR value CONTAINS "${q(loc.textContains)}"`]);
    }
    if (loc.tooltip) out.push(['accessibility id', loc.tooltip]);
  }
  return out;
}

async function tryFind(using: string, value: string): Promise<WebdriverIO.Element | null> {
  try {
    const ref = (await driver.findElement(using, value)) as unknown as Record<string, unknown>;
    if (!ref || ref.error || !(ref[W3C_ID] || ref.ELEMENT)) return null;
    return (await $(ref as never)) as unknown as WebdriverIO.Element;
  } catch {
    return null;
  }
}

/** Waits until the control is found (state wait with short polling, never a fixed sleep) and returns it. */
export async function find(loc: Loc, timeoutMs = waitTimeout()): Promise<WebdriverIO.Element> {
  const list = strategies(loc);
  if (!list.length) throw new Error(`No usable locator for ${describeLoc(loc)} in ${flutterMode()} mode`);
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    for (const [using, value] of list) {
      const el = await tryFind(using, value);
      if (el) return el;
    }
    if (Date.now() > deadline) throw new Error(`Control not found within ${timeoutMs} ms: ${describeLoc(loc)}`);
    await driver.pause(300); // polling interval of the state wait
  }
}

/** True when the control appears within the time given. */
export async function isShown(loc: Loc, timeoutMs = 2000): Promise<boolean> {
  try {
    const el = await find(loc, timeoutMs);
    return await el.isDisplayed().catch(() => true);
  } catch {
    return false;
  }
}

/** Waits until the control is gone. */
export async function waitGone(loc: Loc, timeoutMs = waitTimeout()): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (await isShown(loc, 500)) {
    if (Date.now() > deadline) throw new Error(`Still shown after ${timeoutMs} ms: ${describeLoc(loc)}`);
    await driver.pause(300);
  }
}

/** Scrolls until the control is visible and returns it (driver scroll helpers, never coordinates). */
export async function scrollTo(loc: Loc, direction: 'down' | 'up' = 'down', maxScrolls = 15): Promise<WebdriverIO.Element> {
  if (await isShown(loc, 1000)) return find(loc, 1000);
  const first = strategies(loc)[0];
  if (!first) throw new Error(`No usable locator for ${describeLoc(loc)}`);
  if (flutterMode() === 'integration') {
    await driver.execute('flutter: scrollTillVisible', {
      finder: { using: first[0], value: first[1] }, scrollDirection: direction, maxScrolls,
    });
    return find(loc);
  }
  if (platform() === 'android') {
    const target = loc.text ? `new UiSelector().text("${q(loc.text)}")`
      : loc.textContains ? `new UiSelector().textContains("${q(loc.textContains)}")`
        : loc.label ? `new UiSelector().description("${q(loc.label)}")`
          : loc.id ? `new UiSelector().resourceId("${q(loc.id)}")` : '';
    if (target) {
      await tryFind('-android uiautomator',
        `new UiScrollable(new UiSelector().scrollable(true)).setMaxSearchSwipes(${maxScrolls}).scrollIntoView(${target})`);
    }
    return find(loc);
  }
  for (let i = 0; i < maxScrolls && !(await isShown(loc, 500)); i++) {
    await driver.execute('mobile: scroll', { direction });
  }
  return find(loc);
}

/** Native system UI (permission pop-ups, share sheet) lives outside Flutter: native strategies only. */
export async function findNative(using: string, value: string, timeoutMs = waitTimeout()): Promise<WebdriverIO.Element | null> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const el = await tryFind(using, value);
    if (el) return el;
    if (Date.now() > deadline) return null;
    await driver.pause(300);
  }
}
