import { Button, Card, CardBody } from '@baymeister/ui';
import { useState, type FormEvent } from 'react';
import { login } from '../auth/permissions';

/**
 * Екран входу. Показується замість усього каркаса, поки немає сесії, — тому
 * живе поза роутером і не залежить від реєстру модулів.
 */
export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (e) {
      setError((e as Error).message);
      setPending(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-ground p-6">
      <Card className="w-full max-w-sm">
        <CardBody className="flex flex-col gap-6 py-8">
          <div>
            <h1 className="font-cond text-2xl leading-none font-bold tracking-tight text-ink">
              Baymeister
            </h1>
            <p className="mt-2 text-sm text-ink-muted">Увійдіть, щоб продовжити</p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Email</span>
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Пароль</span>
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
              />
            </label>

            {error ? (
              <p role="alert" className="rounded-bm bg-danger-soft px-3 py-2 text-sm text-danger">
                {error}
              </p>
            ) : null}

            <Button type="submit" disabled={pending || !email || !password}>
              {pending ? 'Вхід…' : 'Увійти'}
            </Button>
          </form>
        </CardBody>
      </Card>
    </main>
  );
}

const inputClass =
  'h-9 w-full rounded-bm border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-faint';
