import {
  identityApi,
  setTokenProvider,
  setUnauthorizedHandler,
  type IdentitySchemas,
} from '@baymeister/api-client';
import { create } from 'zustand';

export type CurrentUser = IdentitySchemas['schemas']['Me'];

type Status = 'restoring' | 'anonymous' | 'authenticated';

interface AuthState {
  status: Status;
  user: CurrentUser | null;
  token: string | null;
}

const TOKEN_KEY = 'bm-token';

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Приватний режим браузера: сесія проживе до перезавантаження вкладки.
  }
}

/**
 * Сесія каркаса.
 *
 * Токен видає identity, перевіряє gateway. Каркас лише зберігає токен і питає
 * /identity/me, хто він такий. Модулі сесії не бачать — токен у запити
 * підставляє api-client, а права каркас передає через usePermissions.
 */
export const useAuth = create<AuthState>(() => {
  const token = readToken();
  return { status: token ? 'restoring' : 'anonymous', user: null, token };
});

setTokenProvider(() => useAuth.getState().token);
setUnauthorizedHandler(() => logout());

/** Відновити сесію після перезавантаження сторінки. */
export async function restoreSession(): Promise<void> {
  if (!useAuth.getState().token) return;

  try {
    const { data, response } = await identityApi.GET('/identity/me');
    if (data) {
      useAuth.setState({ status: 'authenticated', user: data });
      return;
    }
    if (response.status === 401) {
      logout();
      return;
    }
  } catch {
    // Мережа або gateway лежить — нижче.
  }
  // Сервер недоступний, а не відмовив: токен лишається, наступне
  // перезавантаження сторінки спробує ще раз.
  useAuth.setState({ status: 'anonymous', user: null });
}

export async function login(email: string, password: string): Promise<void> {
  const result = await identityApi
    .POST('/identity/auth/login', { body: { email, password } })
    .catch(() => {
      throw new Error('Сервер недоступний. Спробуйте за хвилину.');
    });
  const { data, error } = result;
  if (!data) throw new Error(error?.detail ?? 'Не вдалося увійти');

  writeToken(data.access_token);
  useAuth.setState({ status: 'authenticated', user: data.user, token: data.access_token });
}

export function logout(): void {
  writeToken(null);
  useAuth.setState({ status: 'anonymous', user: null, token: null });
}

function allows(user: CurrentUser | null, required: string[]): boolean {
  if (!user) return false;
  if (user.permissions.includes('*')) return true;
  return required.every((p) => user.permissions.includes(p));
}

/** Чи має поточний користувач усі перелічені права. */
export function usePermissions(required: string[]): boolean {
  const user = useAuth((s) => s.user);
  return allows(user, required);
}

/** Перевірка прав як функція — для меню, де модулів багато. */
export function useCan(): (required: string[]) => boolean {
  const user = useAuth((s) => s.user);
  return (required) => allows(user, required);
}

/** Нереактивна перевірка — для побудови маршрутів поза рендером. */
export function canStatic(required: string[]): boolean {
  return allows(useAuth.getState().user, required);
}
