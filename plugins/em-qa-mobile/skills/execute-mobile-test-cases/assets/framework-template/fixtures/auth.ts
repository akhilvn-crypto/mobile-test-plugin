import { LoginScreen } from '../screens/LoginScreen';
import { credentials } from '../utils/env';

/**
 * Login helpers per role. Values come from .env through test-data/credentials.map.json; nothing is written in a
 * spec. After a successful sign-in the app shows its first signed-in screen; adjust `homeAnchor` in the spec or
 * extend this helper once the exploration shows that screen.
 */
export async function signIn(role: string): Promise<void> {
  const { user, password } = credentials(role);
  const login = new LoginScreen();
  await login.waitUntilShown();
  await login.signIn(user, password);
}
