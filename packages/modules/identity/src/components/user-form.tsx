import { Button, cn } from '@baymeister/ui';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useRoles, type User } from '../api';

const ROLE_IDS = ['owner', 'manager', 'mechanic', 'cashier', 'storekeeper'] as const;

/**
 * Схема дублює обмеження контракту. Це навмисно: користувач бачить помилку до
 * запиту, а бекенд усе одно валідує ще раз — йому не можна довіряти клієнту.
 *
 * Пароль обовʼязковий при створенні і необовʼязковий при редагуванні: порожнє
 * поле означає «не змінювати».
 */
function makeSchema(passwordRequired: boolean) {
  const password = z.string().min(8, 'Щонайменше 8 символів').max(256);
  return z.object({
    email: z.string().email('Некоректна адреса'),
    name: z.string().trim().min(1, 'Вкажіть імʼя').max(200),
    role: z.enum(ROLE_IDS),
    password: passwordRequired ? password : password.or(z.literal('')),
  });
}

export type UserFormValues = z.infer<ReturnType<typeof makeSchema>>;

export interface UserFormProps {
  defaultValues?: Partial<User>;
  mode: 'create' | 'edit';
  submitLabel: string;
  pending?: boolean;
  error?: string | null;
  onSubmit: (values: UserFormValues) => void;
  onCancel?: () => void;
}

export function UserForm({
  defaultValues,
  mode,
  submitLabel,
  pending,
  error,
  onSubmit,
  onCancel,
}: UserFormProps) {
  const roles = useRoles();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<UserFormValues>({
    resolver: zodResolver(makeSchema(mode === 'create')),
    defaultValues: {
      email: defaultValues?.email ?? '',
      name: defaultValues?.name ?? '',
      role: defaultValues?.role ?? 'mechanic',
      password: '',
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Імʼя" error={errors.name?.message} required className="sm:col-span-2">
          <input {...register('name')} className={inputClass} />
        </Field>

        <Field label="Email" error={errors.email?.message} required>
          <input {...register('email')} type="email" autoComplete="off" className={inputClass} />
        </Field>

        <Field label="Роль" error={errors.role?.message} required>
          <select {...register('role')} className={inputClass}>
            {(roles.data ?? ROLE_IDS.map((id) => ({ id, title: id }))).map((role) => (
              <option key={role.id} value={role.id}>
                {role.title}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label={mode === 'create' ? 'Пароль' : 'Новий пароль'}
          hint={mode === 'edit' ? 'Порожньо — не змінювати' : undefined}
          error={errors.password?.message}
          required={mode === 'create'}
        >
          <input
            {...register('password')}
            type="password"
            autoComplete="new-password"
            className={inputClass}
          />
        </Field>
      </div>

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
  hint,
  error,
  required,
  className,
  children,
}: {
  label: string;
  hint?: string;
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
      {error ? (
        <span className="text-xs text-danger">{error}</span>
      ) : hint ? (
        <span className="text-xs text-ink-faint">{hint}</span>
      ) : null}
    </label>
  );
}
