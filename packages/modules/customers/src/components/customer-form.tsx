import { Button, cn } from '@baymeister/ui';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import type { Customer } from '../api';

/**
 * Схема дублює обмеження контракту. Це навмисно: користувач бачить помилку до
 * запиту, а бекенд усе одно валідує ще раз — йому не можна довіряти клієнту.
 */
const schema = z.object({
  type: z.enum(['individual', 'company']),
  name: z.string().min(1, 'Вкажіть імʼя').max(200),
  phone: z
    .string()
    .regex(/^\+[1-9][0-9]{7,14}$/, 'Формат: +380671234567'),
  email: z.string().email('Некоректна адреса').or(z.literal('')),
  tax_id: z.string().max(20).or(z.literal('')),
  notes: z.string().max(2000).or(z.literal('')),
  discount_percent: z.coerce.number().min(0).max(100),
});

export type CustomerFormValues = z.infer<typeof schema>;

export interface CustomerFormProps {
  defaultValues?: Partial<Customer>;
  submitLabel: string;
  pending?: boolean;
  error?: string | null;
  onSubmit: (values: CustomerFormValues) => void;
  onCancel?: () => void;
}

export function CustomerForm({
  defaultValues,
  submitLabel,
  pending,
  error,
  onSubmit,
  onCancel,
}: CustomerFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CustomerFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      type: defaultValues?.type ?? 'individual',
      name: defaultValues?.name ?? '',
      phone: defaultValues?.phone ?? '',
      email: defaultValues?.email ?? '',
      tax_id: defaultValues?.tax_id ?? '',
      notes: defaultValues?.notes ?? '',
      discount_percent: defaultValues?.discount_percent ?? 0,
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Тип" error={errors.type?.message}>
          <select {...register('type')} className={inputClass}>
            <option value="individual">Фізична особа</option>
            <option value="company">Юридична особа</option>
          </select>
        </Field>

        <Field label="Телефон" error={errors.phone?.message} required>
          <input {...register('phone')} placeholder="+380671234567" className={inputClass} />
        </Field>

        <Field label="Імʼя або назва" error={errors.name?.message} required className="sm:col-span-2">
          <input {...register('name')} className={inputClass} />
        </Field>

        <Field label="Email" error={errors.email?.message}>
          <input {...register('email')} type="email" className={inputClass} />
        </Field>

        <Field label="ЄДРПОУ / РНОКПП" error={errors.tax_id?.message}>
          <input {...register('tax_id')} className={inputClass} />
        </Field>

        <Field label="Знижка, %" error={errors.discount_percent?.message}>
          <input
            {...register('discount_percent')}
            type="number"
            step="0.5"
            min="0"
            max="100"
            className={cn(inputClass, 'tabular')}
          />
        </Field>
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
