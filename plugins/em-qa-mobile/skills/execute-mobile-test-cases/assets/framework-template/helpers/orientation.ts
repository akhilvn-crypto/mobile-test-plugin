/** Portrait / landscape. Only for apps that support both (the exploration notes say so). */
export type Orientation = 'PORTRAIT' | 'LANDSCAPE';

export async function rotate(to: Orientation): Promise<void> {
  await driver.setOrientation(to);
  await driver.waitUntil(async () => (await driver.getOrientation()).toUpperCase() === to,
    { timeout: 5000, timeoutMsg: `The screen did not turn to ${to.toLowerCase()}` });
}

export async function current(): Promise<Orientation> {
  return (await driver.getOrientation()).toUpperCase() as Orientation;
}

/** Puts the device back in portrait after a case that rotated it. */
export async function resetToPortrait(): Promise<void> {
  if ((await current()) !== 'PORTRAIT') await rotate('PORTRAIT');
}

/** Window size, for objective layout checks on the connected device. */
export async function screenSize(): Promise<{ width: number; height: number }> {
  return driver.getWindowSize();
}
