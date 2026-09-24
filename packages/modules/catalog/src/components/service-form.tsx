import { Button } from '@baymeister/ui';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import type { Service } from '../api';
import { ErrorNote, Field, HOURS_RE, inputClass, MONEY_RE } from './ui';

/** Дублює обмеження контракту: помилка видна до запиту, бекенд перевірить ще раз. */
const schema = z.object({
  code: z.string().trim().min(1, 'Вкажіть код').max(20),
  name: z.string().trim().min(1, 'Вкажіть назву').max(200),
  category: z.string().trim().min(1, 'Вкажіть категорію').max(60),
  norm_hours: z.string().trim().regex(HOURS_RE, 'Напр. 1,5'),
  fixed_price: z.string().trim().regex(MONEY_RE, 'Напр. 600 або 600,50').or(z.literal('')),
});

export type ServiceFormValues = z.infer<typeof schema>;

export function ServiceForm({
  service,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  service?: Service;
  pending?: boolean;
  error?: string | null;
  onSubmit: (values: ServiceFormValues) => void;
  onCancel: () => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ServiceFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      code: service?.code ?? '',
      name: service?.name ?? '',
      category: service?.category ?? '',
      norm_hours: service?.norm_hours ?? '',
      fixed_price: service?.fixed_price ?? '',
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="Код" error={errors.code?.message} required>
          <input {...register('code')} placeholder="ENG-OIL" className={`${inputClass} uppercase`} />
        </Field>
        <Field label="Назва" error={errors.name?.message} required className="sm:col-span-3">
          <input {...register('name')} placeholder="Заміна моторної оливи" className={inputClass} />
        </Field>
        <Field label="Категорія" error={errors.category?.message} required className="sm:col-span-2">
          <input {...register('category')} placeholder="Двигун" className={inputClass} />
        </Field>
        <Field label="Нормо-години" error={errors.norm_hours?.message} required>
          <input {...register('norm_hours')} inputMode="decimal" className={`${inputClass} tabular`} />
        </Field>
        <Field label="Фіксована ціна, ₴" error={errors.fixed_price?.message}>
          <input
            {...register('fixed_price')}
            inputMode="decimal"
            placeholder="за ставкою"
            className={`${inputClass} tabular`}
          />
        </Field>
      </div>

      <ErrorNote message={error} />

      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          {pending ? 'Збереження…' : service ? 'Зберегти' : 'Додати'}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Скасувати
        </Button>
      </div>
    </form>
  );
}
