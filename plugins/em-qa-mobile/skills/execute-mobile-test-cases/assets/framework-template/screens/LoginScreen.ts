import { BaseScreen } from './BaseScreen';
import type { Loc } from '../utils/flutter';

/**
 * Generic sign-in screen. Adjust the labels to the app from Exploration/.../screens/login.json
 * (keep the method names: fixtures/auth.ts uses signIn()).
 */
export class LoginScreen extends BaseScreen {
  protected readonly anchor: Loc = { label: 'Sign in', text: 'Sign in', name: 'Sign in screen' };

  readonly email: Loc = { label: 'Email', key: 'email', name: 'Email field' };
  readonly password: Loc = { label: 'Password', key: 'password', name: 'Password field' };
  readonly signInButton: Loc = { label: 'Sign in', key: 'sign_in', text: 'Sign in', name: 'Sign in button' };

  async enterEmail(value: string): Promise<void> {
    await this.enter(this.email, value);
  }

  async enterPassword(value: string): Promise<void> {
    await this.enter(this.password, value);
  }

  async tapSignIn(): Promise<void> {
    await this.hideKeyboard();
    await this.tap(this.signInButton);
  }

  async signIn(user: string, password: string): Promise<void> {
    await this.enterEmail(user);
    await this.enterPassword(password);
    await this.tapSignIn();
  }
}
