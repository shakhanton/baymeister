import type { AppModule } from '@baymeister/module-kit';
import { Badge, cn } from '@baymeister/ui';
import { NavLink } from 'react-router';
import { usePermissions } from '../auth/permissions';
import { Icon } from './icon';

/**
 * Пункт бічного меню.
 *
 * Готовий блок — посилання. Неготовий — <span> з aria-disabled, а НЕ <a> з
 * pointer-events:none: вимкнене посилання все одно ловить фокус з клавіатури і
 * читається скрінрідером як робоче.
 */
export function NavItem({ module }: { module: AppModule }) {
  const allowed = usePermissions(module.permissions);
  const target = module.routes[0];

  if (module.status === 'ready' && allowed && target) {
    return (
      <NavLink
        to={target.path}
        className={({ isActive }) =>
          cn(
            'flex items-center gap-2.5 rounded-bm px-3 py-2 text-sm transition-colors',
            isActive
              ? 'bg-accent-soft font-medium text-accent'
              : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
          )
        }
      >
        <Icon name={module.icon} className="size-4 shrink-0" />
        <span className="truncate">{module.title}</span>
      </NavLink>
    );
  }

  return (
    <span
      aria-disabled="true"
      title={module.description ?? 'Блок ще не інтегрований'}
      className="flex cursor-default items-center gap-2.5 rounded-bm px-3 py-2 text-sm text-planned select-none"
    >
      <Icon name={module.icon} className="size-4 shrink-0 opacity-50" />
      <span className="truncate">{module.title}</span>
      {module.status === 'in-progress' ? (
        <Badge tone="wip" className="ml-auto">
          у розробці
        </Badge>
      ) : null}
    </span>
  );
}
