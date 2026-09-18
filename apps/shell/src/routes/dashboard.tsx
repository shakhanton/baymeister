import { Card, CardBody, CardHeader, CardTitle } from '@baymeister/ui';
import { Link } from 'react-router';
import { registry } from '../modules/registry';

export default function Dashboard() {
  const ready = registry.filter((m) => m.status === 'ready').length;
  const inProgress = registry.filter((m) => m.status === 'in-progress').length;
  const planned = registry.filter((m) => m.status === 'planned').length;

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <section className="grid gap-4 sm:grid-cols-3">
        <Stat label="Готові блоки" value={ready} tone="text-ready" />
        <Stat label="У розробці" value={inProgress} tone="text-wip" />
        <Stat label="Заплановані" value={planned} tone="text-planned" />
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Каркас працює</CardTitle>
        </CardHeader>
        <CardBody className="flex flex-col gap-3 text-sm leading-relaxed text-ink-muted">
          <p>
            Меню ліворуч показує всі {registry.length} блоків продукту. Сірі пункти —
            блоки, яких ще немає: їхні маршрути не зареєстровані, тому відкрити їх
            неможливо навіть за прямим посиланням.
          </p>
          <p>
            Щоб блок ожив, у його маніфесті треба змінити <code className="font-mono text-ink">status</code>{' '}
            на <code className="font-mono text-ink">'ready'</code> і додати маршрути. Більше
            в каркасі не змінюється нічого.
          </p>
          <p>
            <Link to="/roadmap" className="text-accent underline underline-offset-2">
              Подивитись стан усіх блоків
            </Link>
          </p>
        </CardBody>
      </Card>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <Card>
      <CardBody>
        <div className="font-mono text-[11px] tracking-wider text-ink-faint uppercase">
          {label}
        </div>
        <div className={`mt-1 font-cond text-4xl leading-none font-bold tabular ${tone}`}>
          {value}
        </div>
      </CardBody>
    </Card>
  );
}
