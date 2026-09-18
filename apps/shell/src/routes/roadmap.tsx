import type { ModuleStatus } from '@baymeister/module-kit';
import { NAV_GROUPS } from '@baymeister/module-kit';
import { Badge } from '@baymeister/ui';
import { registry } from '../modules/registry';

const TONE: Record<ModuleStatus, 'ready' | 'wip' | 'planned'> = {
  ready: 'ready',
  'in-progress': 'wip',
  planned: 'planned',
};

const LABEL: Record<ModuleStatus, string> = {
  ready: 'готовий',
  'in-progress': 'у розробці',
  planned: 'запланований',
};

const GROUP_TITLE = new Map(NAV_GROUPS.map((g) => [g.id, g.title]));

export default function Roadmap() {
  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <p className="max-w-2xl text-sm leading-relaxed text-ink-muted">
        Повний склад продукту. Кожен рядок — вертикальний блок: бекенд-сервіс,
        контракт і фронтенд-модуль в одному володінні.
      </p>

      <div className="overflow-x-auto rounded-bm border border-line bg-surface">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="bg-surface-2">
              {['Блок', 'Розділ', 'Призначення', 'Стан'].map((h) => (
                <th
                  key={h}
                  className="border-b border-line-strong px-4 py-3 text-left font-mono text-[11px] font-medium tracking-wider text-ink-faint uppercase"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {registry.map((module) => (
              <tr key={module.id} className="border-b border-line last:border-0">
                <td className="px-4 py-3 align-top">
                  <div className="font-medium text-ink">{module.title}</div>
                  <div className="font-mono text-xs text-ink-faint">{module.id}</div>
                </td>
                <td className="px-4 py-3 align-top text-ink-muted">
                  {GROUP_TITLE.get(module.nav.group)}
                </td>
                <td className="max-w-md px-4 py-3 align-top leading-relaxed text-ink-muted">
                  {module.description}
                </td>
                <td className="px-4 py-3 align-top">
                  <Badge tone={TONE[module.status]}>{LABEL[module.status]}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs leading-relaxed text-ink-faint">
        Сервіси <span className="font-mono">gateway</span> і{' '}
        <span className="font-mono">files</span> у списку відсутні — вони не мають
        інтерфейсу. Опис у <span className="font-mono">docs/architecture.md</span>.
      </p>
    </div>
  );
}
