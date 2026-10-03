import { startFrom as start, type AppState } from '../helpers/appState';
import { signIn } from './auth';

export { manualCheck, blockedCheck } from '../reporters/results-reporter';
export { credentials } from '../utils/env';
export { uniqueEmail, uniqueName, uniquePhone, stamp } from '../utils/data';
export { signIn };
export type { AppState };

/**
 * Puts the app in the state the case declares: 'fresh install', 'logged out' or 'logged in' (with a role).
 *   await startFrom('logged in', 'admin');
 */
export function startFrom(state: AppState, role?: string): Promise<void> {
  return start(state, role, signIn);
}
