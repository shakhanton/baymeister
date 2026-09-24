import { Button, cn } from '@baymeister/ui';
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useCustomerSearch, type Vehicle } from '../api';

/**
 * Схема дублює обмеження контракту. Це навмисно: користувач бачить помилку до
 * запиту, а бекенд усе одно валідує ще раз — йому не можна довіряти клієнту.
 * Номер і VIN бекенд нормалізує сам, тому тут перевіряється лише форма.
 */
const optionalNumber = (min: number, max: number) =>
  z.preprocess(
    (v) => (v === '' || v === null || v === undefined ? undefined : Number(v)),
    z.number().int('Ціле число').min(min).max(max).optional(),
  );

const schema = z.object({
  customer_id: z.string().uuid('Оберіть власника'),
  plate: z.string().trim().min(2, 'Вкажіть держномер').max(16),
  vin: z
    .string()
    .trim()
    .regex(/^[A-HJ-NPR-Za-hj-npr-z0-9]{17}$/, '17 символів, без I, O, Q')
    .or(z.literal('')),
  make: z.string().trim().min(1, 'Вкажіть марку').max(60),
  model: z.string().trim().min(1, 'Вкажіть модель').max(60),
  year: optionalNumber(1900, 2100),
  color: z.string().max(40).or(z.literal('')),
  mileage_km: optionalNumber(0, 9_999_999),
  notes: z.string().max(2000).or(z.literal('')),
});

export type VehicleFormValues = z.infer<typeof schema>;

export interface VehicleFormProps {
  defaultValues?: Partial<Vehicle>;
  mode: 'create' | 'edit';
  submitLabel: string;
  pending?: boolean;
  error?: string | null;
  onSubmit: (values: VehicleFormValues) => void;
  onCancel?: () => void;
}

export function VehicleForm({
  defaultValues,
  mode,
  submitLabel,
  pending,
  error,
  onSubmit,
  onCancel,
}: VehicleFormProps) {
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<VehicleFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      customer_id: defaultValues?.customer_id ?? '',
      plate: defaultValues?.plate ?? '',
      vin: defaultValues?.vin ?? '',
      make: defaultValues?.make ?? '',
      model: defaultValues?.model ?? '',
      year: defaultValues?.year ?? undefined,
      color: defaultValues?.color ?? '',
      mileage_km: undefined,
      notes: defaultValues?.notes ?? '',
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <input type="hidden" {...register('customer_id')} />
      <OwnerPicker
        initial={
          defaultValues?.customer_id
            ? { name: defaultValues.customer_name ?? '', phone: defaultValues.customer_phone ?? '' }
            : null
        }
        error={errors.customer_id?.message}
        onPick={(id) => setValue('customer_id', id, { shouldValidate: true })}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Держномер" error={errors.plate?.message} required>
          <input {...register('plate')} placeholder="AA1234BC" className={cn(inputClass, 'uppercase')} />
        </Field>

        <Field label="VIN" error={errors.vin?.message}>
          <input {...register('vin')} className={cn(inputClass, 'font-mono uppercase')} />
        </Field>

        <Field label="Марка" error={errors.make?.message} required>
          <input {...register('make')} placeholder="Volkswagen" className={inputClass} />
        </Field>

        <Field label="Модель" error={errors.model?.message} required>
          <input {...register('model')} placeholder="Golf" className={inputClass} />
        </Field>

        <Field label="Рік" error={errors.year?.message}>
          <input {...register('year')} type="number" className={cn(inputClass, 'tabular')} />
        </Field>

        <Field label="Колір" error={errors.color?.message}>
          <input {...register('color')} className={inputClass} />
        </Field>

        {mode === 'create' ? (
          <Field label="Пробіг при прийманні, км" error={errors.mileage_km?.message}>
            <input {...register('mileage_km')} type="number" className={cn(inputClass, 'tabular')} />
          </Field>
        ) : null}
      </div>

      <Field label="Примітки" error={errors.notes?.message}>
        <textarea {...register('notes')} rows={3} className={cn(inputClass, 'resize-y')} />
      </Field>

      {error ? (
        <p role="alert" className="rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          {pending ? 'Збереження…' : submitLabel}
        </Button>
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Скасувати
          </Button>
        ) : null}
      </div>
    </form>
  );
}

/**
 * Власник обирається пошуком — клієнтів у сервісі сотні, випадаючий список
 * не підходить. Зміна власника в існуючого авто — це продаж.
 */
function OwnerPicker({
  initial,
  error,
  onPick,
}: {
  initial: { name: string; phone: string } | null;
  error?: string;
  onPick: (customerId: string) => void;
}) {
  const [picked, setPicked] = useState(initial);
  const [search, setSearch] = useState('');
  const results = useCustomerSearch(search);

  if (picked) {
    return (
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink">
          Власник<span className="text-danger"> *</span>
        </span>
        <div className="flex items-center gap-3 rounded-bm border border-line-strong px-3 py-2 text-sm">
          <span className="font-medium text-ink">{picked.name}</span>
          <span className="font-mono text-ink-muted">{picked.phone}</span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => {
              setPicked(null);
              setSearch('');
            }}
          >
            Змінити
          </Button>
        </div>
      </div>
    );
  }

  return (
    <Field label="Власник" error={error} required>
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Імʼя або телефон клієнта"
        className={inputClass}
      />
      {search.trim().length >= 2 ? (
        <ul className="mt-1 overflow-hidden rounded-bm border border-line bg-surface" role="listbox">
          {results.isError ? (
            <li className="px-3 py-2 text-sm text-danger">{results.error.message}</li>
          ) : results.data && results.data.length === 0 ? (
            <li className="px-3 py-2 text-sm text-ink-muted">Нікого не знайдено</li>
          ) : (
            results.data?.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected="false"
                  className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-surface-2"
                  onClick={() => {
                    setPicked({ name: c.name, phone: c.phone });
                    onPick(c.id);
                  }}
                >
                  <span className="text-ink">{c.name}</span>
                  <span className="font-mono text-ink-muted">{c.phone}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </Field>
  );
}

const inputClass =
  'h-9 w-full rounded-bm border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-faint';

function Field({
  label,
  error,
  required,
  className,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn('flex flex-col gap-1.5', className)}>
      <span className="text-sm font-medium text-ink">
        {label}
        {required ? <span className="text-danger"> *</span> : null}
      </span>
      {children}
      {error ? <span className="text-xs text-danger">{error}</span> : null}
    </label>
  );
}
