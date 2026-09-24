import { Badge, Button, Card, CardBody, CardHeader, CardTitle, EmptyState } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { useCreateSupplier, useNeeds, useSuppliers, useUpdateSupplier, type Supplier } from '../api';
import { ErrorNote, inputClass, ProcurementTabs, thClass } from '../components/ui';

const EDRPOU_RE = /^(\d{8}|\d{10})$/;
const PHONE_RE = /^\+[1-9][0-9]{7,14}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Draft = { name: string; edrpou: string; contact: string; phone: string; email: string; note: string };

const EMPTY: Draft = { name: '', edrpou: '', contact: '', phone: '', email: '', note: '' };

function fromSupplier(s: Supplier): Draft {
  return {
    name: s.name,
    edrpou: s.edrpou ?? '',
    contact: s.contact ?? '',
    phone: s.phone ?? '',
    email: s.email ?? '',
    note: s.note ?? '',
  };
}

/** Порожнє поле — null; телефон без пробілів і дужок. */
function toBody(d: Draft) {
  const opt = (v: string) => v.trim() || null;
  return {
    name: d.name.trim(),
    edrpou: opt(d.edrpou),
    contact: opt(d.contact),
    phone: opt(d.phone.replace(/[\s()-]/g, '')),
    email: opt(d.email),
    note: opt(d.note),
  };
}

function problems(d: Draft): Partial<Record<keyof Draft, string>> {
  const b = toBody(d);
  const out: Partial<Record<keyof Draft, string>> = {};
  if (!b.name) out.name = 'Вкажіть назву';
  if (b.edrpou && !EDRPOU_RE.test(b.edrpou)) out.edrpou = '8 цифр ЄДРПОУ або 10 цифр РНОКПП';
  if (b.phone && !PHONE_RE.test(b.phone)) out.phone = 'У форматі +380501112233';
  if (b.email && !EMAIL_RE.test(b.email)) out.email = 'Перевірте адресу';
  return out;
}

export default function SuppliersPage() {
  const [search, setSearch] = useState('');
  const [archived, setArchived] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const query = useSuppliers(search, archived);
  const needs = useNeeds();

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <ProcurementTabs needs={needs.data?.length} />

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Назва, ЄДРПОУ, телефон"
          aria-label="Пошук постачальників"
          className="h-9 w-72 rounded-bm border border-line-strong bg-surface px-3 text-sm placeholder:text-ink-faint"
        />
        <label className="flex items-center gap-2 text-sm text-ink-muted">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
          Показати архівних
        </label>
        <Button className="ml-auto" onClick={() => setAdding((v) => !v)}>
          {adding ? 'Згорнути' : 'Додати постачальника'}
        </Button>
      </div>

      {adding ? (
        <Card>
          <CardHeader>
            <CardTitle>Новий постачальник</CardTitle>
          </CardHeader>
          <CardBody>
            <SupplierForm onDone={() => setAdding(false)} />
          </CardBody>
        </Card>
      ) : null}

      <ErrorNote message={query.error?.message} />

      {query.data && query.data.items.length === 0 ? (
        <EmptyState
          title={search ? 'Нічого не знайдено' : 'Постачальників ще немає'}
          description={search ? 'Спробуйте інший запит.' : 'Додайте першого — у кого купуєте запчастини.'}
        />
      ) : null}

      {query.data && query.data.items.length > 0 ? (
        <div className="overflow-x-auto rounded-bm border border-line bg-surface">
          <table className="w-full min-w-[760px] border-collapse text-sm">
            <thead>
              <tr className="bg-surface-2">
                {['Назва', 'ЄДРПОУ', 'Контакт', 'Телефон', ''].map((h) => (
                  <th key={h} className={thClass}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((s) =>
                editing === s.id ? (
                  <tr key={s.id} className="border-b border-line last:border-0">
                    <td colSpan={5} className="bg-surface-2 px-4 py-4">
                      <SupplierForm supplier={s} onDone={() => setEditing(null)} />
                    </td>
                  </tr>
                ) : (
                  <tr key={s.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <span className="font-medium text-ink">{s.name}</span>
                      {!s.active ? (
                        <Badge className="ml-2">архів</Badge>
                      ) : null}
                      {s.note ? <div className="text-xs text-ink-faint">{s.note}</div> : null}
                    </td>
                    <td className="px-4 py-3 font-mono text-ink-muted">{s.edrpou ?? '—'}</td>
                    <td className="px-4 py-3 text-ink-muted">
                      {s.contact ?? '—'}
                      {s.email ? <div className="text-xs">{s.email}</div> : null}
                    </td>
                    <td className="px-4 py-3 tabular text-ink-muted">{s.phone ?? '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(s.id)} aria-label={`Змінити: ${s.name}`}>
                        Змінити
                      </Button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function SupplierForm({ supplier, onDone }: { supplier?: Supplier; onDone: () => void }) {
  const [draft, setDraft] = useState<Draft>(supplier ? fromSupplier(supplier) : EMPTY);
  const [touched, setTouched] = useState(false);
  const create = useCreateSupplier();
  const update = useUpdateSupplier();
  const mutation = supplier ? update : create;
  const errors = touched ? problems(draft) : {};

  function set<K extends keyof Draft>(key: K) {
    return (e: { target: { value: string } }) => setDraft((d) => ({ ...d, [key]: e.target.value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (Object.keys(problems(draft)).length) return;
    if (supplier) update.mutate({ id: supplier.id, ...toBody(draft) }, { onSuccess: onDone });
    else create.mutate(toBody(draft), { onSuccess: onDone });
  }

  const field = (key: keyof Draft, label: string, extra?: { placeholder?: string; className?: string }) => (
    <label className={`flex flex-col gap-1.5 ${extra?.className ?? ''}`}>
      <span className="text-sm font-medium text-ink">{label}</span>
      <input
        value={draft[key]}
        onChange={set(key)}
        placeholder={extra?.placeholder}
        aria-invalid={errors[key] ? true : undefined}
        className={inputClass}
      />
      {errors[key] ? <span className="text-xs text-danger">{errors[key]}</span> : null}
    </label>
  );

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 sm:grid-cols-3" noValidate>
      {field('name', 'Назва', { className: 'sm:col-span-2', placeholder: 'ТОВ «Автотехнікс»' })}
      {field('edrpou', 'ЄДРПОУ')}
      {field('contact', 'Контактна особа')}
      {field('phone', 'Телефон', { placeholder: '+380501112233' })}
      {field('email', 'Email')}
      {field('note', 'Примітка', { className: 'sm:col-span-3', placeholder: 'Напр. доставка вт і пт, відстрочка 14 днів' })}
      <div className="flex flex-col gap-2 sm:col-span-3">
        <ErrorNote message={mutation.error?.message} />
        <div className="flex gap-2">
          <Button type="submit" disabled={mutation.isPending}>
            {supplier ? 'Зберегти' : 'Додати'}
          </Button>
          {supplier ? (
            <Button
              type="button"
              variant="outline"
              disabled={update.isPending}
              onClick={() => update.mutate({ id: supplier.id, active: !supplier.active }, { onSuccess: onDone })}
            >
              {supplier.active ? 'В архів' : 'Повернути з архіву'}
            </Button>
          ) : null}
          <Button type="button" variant="ghost" onClick={onDone}>
            Скасувати
          </Button>
        </div>
      </div>
    </form>
  );
}
