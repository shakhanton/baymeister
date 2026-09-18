import type { ComponentType } from 'react';

/**
 * Життєвий цикл блоку.
 *
 * `planned`     — блок описаний, коду немає. Пункт меню сірий.
 * `in-progress` — код пишеться, але в продакшн не йде. Пункт меню сірий.
 * `ready`       — блок інтегрований. Пункт меню клікабельний, маршрути живі.
 *
 * Це єдине поле, яке треба змінити, щоб інтегрувати готовий блок.
 */
export type ModuleStatus = 'planned' | 'in-progress' | 'ready';

/** Групи бічного меню. Порядок груп задає NAV_GROUPS. */
export type NavGroupId =
  | 'operations'
  | 'catalog'
  | 'warehouse'
  | 'finance'
  | 'insights'
  | 'settings';

export interface NavGroup {
  id: NavGroupId;
  title: string;
  order: number;
}

/** Порядок і назви груп меню. Змінюється тільки разом із дизайном навігації. */
export const NAV_GROUPS: readonly NavGroup[] = [
  { id: 'operations', title: 'Операції', order: 10 },
  { id: 'catalog', title: 'Довідники', order: 20 },
  { id: 'warehouse', title: 'Склад', order: 30 },
  { id: 'finance', title: 'Фінанси', order: 40 },
  { id: 'insights', title: 'Аналітика', order: 50 },
  { id: 'settings', title: 'Налаштування', order: 60 },
] as const;

export interface ModuleRoute {
  /** Абсолютний шлях, напр. '/work-orders/:id'. */
  path: string;
  /** Лінива підвантаження екрана. Код неготового блоку в бандл не потрапляє. */
  lazy: () => Promise<{ default: ComponentType }>;
}

export interface AppModule {
  /** Стабільний ідентифікатор, збігається з іменем сервісу: 'work-orders'. */
  id: string;
  /** Підпис у меню. */
  title: string;
  /** Ім'я іконки з набору каркаса. */
  icon: string;
  status: ModuleStatus;
  nav: { group: NavGroupId; order: number };
  /** Права, без яких пункт меню не показується взагалі. */
  permissions: string[];
  /** Порожньо, поки status !== 'ready'. */
  routes: ModuleRoute[];
  /** Одне речення для сторінки-заглушки і для документації. */
  description?: string;
}

/** Перевірка прав. Каркас передає реалізацію, модуль її не знає. */
export type PermissionCheck = (permissions: string[]) => boolean;
