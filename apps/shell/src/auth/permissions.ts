import { create } from 'zustand';

export interface CurrentUser {
  id: string;
  name: string;
  role: string;
  /** Список прав. '*' означає повний доступ. */
  permissions: string[];
}

interface AuthState {
  user: CurrentUser | null;
  setUser: (user: CurrentUser | null) => void;
}

/**
 * ЗАГЛУШКА ФАЗИ 0.
 *
 * Поки блок `identity` не готовий, каркас працює під вигаданим власником із
 * повним доступом. Коли identity стане `ready`, цей об'єкт замінюється
 * відповіддю /api/identity/me, а решта каркаса не змінюється — вона вже читає
 * користувача через usePermissions.
 */
const DEV_USER: CurrentUser = {
  id: 'dev',
  name: 'Власник',
  role: 'owner',
  permissions: ['*'],
};

export const useAuth = create<AuthState>((set) => ({
  user: DEV_USER,
  setUser: (user) => set({ user }),
}));

/** Чи має поточний користувач усі перелічені права. */
export function usePermissions(required: string[]): boolean {
  const user = useAuth((s) => s.user);
  if (!user) return false;
  if (user.permissions.includes('*')) return true;
  return required.every((p) => user.permissions.includes(p));
}

/** Неріактивна перевірка — для побудови маршрутів поза рендером. */
export function canStatic(required: string[]): boolean {
  const user = useAuth.getState().user;
  if (!user) return false;
  if (user.permissions.includes('*')) return true;
  return required.every((p) => user.permissions.includes(p));
}
