import { Badge, Button, Card, CardBody, CardHeader, CardTitle } from '@baymeister/ui';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useArchiveCustomer, useCustomer, useUpdateCustomer } from '../api';
import { CustomerForm, type CustomerFormValues } from '../components/customer-form';

export default function CustomerDetail() {
  const { customerId = '' } = useParams();
  const [editing, setEditing] = useState(false);

  const query = useCustomer(customerId);
  const update = useUpdateCustomer(customerId);
  const archive = useArchiveCustomer(customerId);

  if (query.isPending) {
    return <div className="h-40 max-w-3xl animate-pulse rounded-bm bg-surface-2" role="status" />;
  }

  if (query.isError) {
    return (
      <div className="flex max-w-3xl flex-col gap-3">
        <p role="alert" className="rounded-bm bg-danger-soft px-4 py-3 text-sm text-danger">
          {query.error.message}
        </p>
        <Link to="/customers" className="text-sm text-accent underline underline-offset-2">
          ← До списку клієнтів
        </Link>
      </div>
    );
  }

  const customer = query.data;

  async function handleSave(values: CustomerFormValues) {
    await update.mutateAsync({
      type: values.type,
      name: values.name,
      phone: values.phone,
      email: values.email || null,
      tax_id: values.tax_id || null,
      notes: values.notes || null,
      discount_percent: values.discount_percent,
    });
    setEditing(false);
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <Link to="/customers" className="text-sm text-accent underline underline-offset-2">
        ← До списку клієнтів
      </Link>

      <Card>
        <CardHeader className="flex flex-wrap items-center gap-3">
          <CardTitle>{customer.name}</CardTitle>
          <Badge tone={customer.type === 'company' ? 'accent' : 'neutral'}>
            {customer.type === 'company' ? 'юр. особа' : 'фіз. особа'}
          </Badge>
          {customer.archived_at ? <Badge tone="planned">в архіві</Badge> : null}

          {!customer.archived_at ? (
            <div className="ml-auto flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditing((v) => !v)}>
                {editing ? 'Скасувати' : 'Редагувати'}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={archive.isPending}
                onClick={() => archive.mutate()}
              >
                Архівувати
              </Button>
            </div>
          ) : null}
        </CardHeader>

        <CardBody>
          {editing ? (
            <CustomerForm
              defaultValues={customer}
              submitLabel="Зберегти"
              pending={update.isPending}
              error={update.error?.message ?? null}
              onSubmit={handleSave}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
              <Row label="Телефон" value={customer.phone} mono />
              <Row label="Email" value={customer.email} />
              <Row label="ЄДРПОУ / РНОКПП" value={customer.tax_id} mono />
              <Row
                label="Знижка"
                value={customer.discount_percent > 0 ? `${customer.discount_percent}%` : null}
              />
              <Row label="Примітки" value={customer.notes} className="sm:col-span-2" />
            </dl>
          )}

          {archive.isError ? (
            <p role="alert" className="mt-4 rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
              {archive.error.message}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <p className="text-xs text-ink-faint">
        Автомобілі та наряди цього клієнта зʼявляться тут, коли блоки{' '}
        <span className="font-mono">vehicles</span> і{' '}
        <span className="font-mono">work-orders</span> стануть готовими.
      </p>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
  className,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="font-mono text-[11px] tracking-wider text-ink-faint uppercase">{label}</dt>
      <dd className={`mt-0.5 text-sm text-ink ${mono ? 'font-mono' : ''}`}>{value || '—'}</dd>
    </div>
  );
}
