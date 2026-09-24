import { Button } from '@baymeister/ui';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import type { Part } from '../api';
import { ErrorNote, Field, inputClass, MONEY_RE, UNIT_LABEL } from './ui';

const schema = z.object({
  sku: z.string().trim().min(1, 'Вкажіть артикул').max(40),
  brand: z.string().trim().min(1, 'Вкажіть бренд').max(60),
  name: z.string().trim().min(1, 'Вкажіть назву').max(200),
  unit: z.enum(['pcs', 'l', 'kg', 'm', 'set']),
  price: z.string().trim().regex(MONEY_RE, 'Напр. 245 або 245,50'),
});

export type PartFormValues = z.infer<typeof schema>;

export function PartForm({
  part,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  part?: Part;
  pending?: boolean;
  error?: string | null;
  onSubmit: (values: PartFormValues) => void;
  onCancel: () => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<PartFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      sku: part?.sku ?? '',
      brand: part?.brand ?? '',
      name: part?.name ?? '',
      unit: part?.unit ?? 'pcs',
      price: part?.price ?? '',
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="Артикул" error={errors.sku?.message} required>
          <input {...register('sku')} placeholder="OC90" className={`${inputClass} font-mono uppercase`} />
        </Field>
        <Field label="Бренд" error={errors.brand?.message} required>
          <input {...register('brand')} placeholder="MAHLE" className={`${inputClass} uppercase`} />
        </Field>
        <Field label="Назва" error={errors.name?.message} required className="sm:col-span-2">
          <input {...register('name')} placeholder="Фільтр оливний" className={inputClass} />
        </Field>
        <Field label="Одиниця" error={errors.unit?.message} required>
          <select {...register('unit')} className={inputClass}>
            {Object.entries(UNIT_LABEL).map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Ціна, ₴" error={errors.price?.message} required>
          <input {...register('price')} inputMode="decimal" className={`${inputClass} tabular`} />
        </Field>
      </div>

      <ErrorNote message={error} />

      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          {pending ? 'Збереження…' : part ? 'Зберегти' : 'Додати'}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Скасувати
        </Button>
      </div>
    </form>
  );
}
