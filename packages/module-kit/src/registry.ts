import type { AppModule, NavGroupId, PermissionCheck } from './types';
import { NAV_GROUPS } from './types';

/**
 * Блок вважається живим, якщо він готовий І користувач має права.
 * Обидві умови обов'язкові — готовий блок без прав так само не відкривається.
 */
export function isLive(module: AppModule, can: PermissionCheck): boolean {
  return module.status === 'ready' && can(module.permissions);
}

/**
 * Маршрути тільки живих блоків.
 *
 * Маршрути неготових блоків не реєструються взагалі — незавершений код не може
 * зламати навігацію, навіть якщо вже лежить у репозиторії.
 */
export function liveRoutes(registry: AppModule[], can: PermissionCheck) {
  return registry.filter((m) => isLive(m, can)).flatMap((m) => m.routes);
}

export interface NavSection {
  id: NavGroupId;
  title: string;
  modules: AppModule[];
}

/**
 * Меню: усі блоки, на які користувач має права — і готові, і заглушки.
 * Групи без жодного видимого блоку відкидаються.
 */
export function navSections(registry: AppModule[], can: PermissionCheck): NavSection[] {
  const visible = registry.filter((m) => can(m.permissions));

  return [...NAV_GROUPS]
    .sort((a, b) => a.order - b.order)
    .map((group) => ({
      id: group.id,
      title: group.title,
      modules: visible
        .filter((m) => m.nav.group === group.id)
        .sort((a, b) => a.nav.order - b.nav.order),
    }))
    .filter((section) => section.modules.length > 0);
}

/** Падає на етапі збірки, якщо два блоки взяли однаковий id або шлях. */
export function assertRegistryIsValid(registry: AppModule[]): void {
  const ids = new Set<string>();
  const paths = new Set<string>();

  for (const module of registry) {
    if (ids.has(module.id)) {
      throw new Error(`Дубль id модуля: ${module.id}`);
    }
    ids.add(module.id);

    if (module.status !== 'ready' && module.routes.length > 0) {
      throw new Error(
        `Модуль ${module.id} має маршрути, але status='${module.status}'. ` +
          `Маршрути додаються разом зі status='ready'.`,
      );
    }

    if (module.status === 'ready' && module.routes.length === 0) {
      throw new Error(
        `Модуль ${module.id} має status='ready', але жодного маршруту. ` +
          `Готовий блок мусить мати хоча б один екран.`,
      );
    }

    for (const route of module.routes) {
      if (paths.has(route.path)) {
        throw new Error(`Дубль маршруту ${route.path} у модулі ${module.id}`);
      }
      paths.add(route.path);
    }
  }
}
