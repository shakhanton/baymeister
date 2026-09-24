import { navSections } from '@baymeister/module-kit';
import { cn } from '@baymeister/ui';
import { NavLink } from 'react-router';
import { useCan } from '../auth/permissions';
import { registry } from '../modules/registry';
import { Icon } from './icon';
import { NavItem } from './nav-item';

export function Sidebar() {
  const can = useCan();
  const sections = navSections(registry, can);

  const shellLink = ({ isActive }: { isActive: boolean }) =>
    cn(
      'flex items-center gap-2.5 rounded-bm px-3 py-2 text-sm transition-colors',
      isActive
        ? 'bg-accent-soft font-medium text-accent'
        : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
    );

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex h-14 items-center gap-2 border-b border-line px-5">
        <span className="font-cond text-xl leading-none font-bold tracking-tight text-ink">
          Baymeister
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Основна навігація">
        <NavLink to="/" end className={shellLink}>
          <Icon name="dashboard" className="size-4 shrink-0" />
          <span>Огляд</span>
        </NavLink>

        {sections.map((section) => (
          <div key={section.id} className="mt-6 first:mt-4">
            <h2 className="px-3 pb-1.5 font-mono text-[11px] tracking-wider text-ink-faint uppercase">
              {section.title}
            </h2>
            <div className="flex flex-col gap-0.5">
              {section.modules.map((module) => (
                <NavItem key={module.id} module={module} />
              ))}
            </div>
          </div>
        ))}

        <div className="mt-6 border-t border-line pt-4">
          <NavLink to="/roadmap" className={shellLink}>
            <Icon name="map" className="size-4 shrink-0" />
            <span>Стан блоків</span>
          </NavLink>
        </div>
      </nav>
    </aside>
  );
}
