import { useAuth } from '../auth/permissions';

export function Header({ title }: { title: string }) {
  const user = useAuth((s) => s.user);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-6">
      <h1 className="font-cond text-lg leading-none font-semibold text-ink">{title}</h1>
      {user ? (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-ink-muted">{user.name}</span>
          <span
            className="flex size-8 items-center justify-center rounded-full bg-accent-soft font-mono text-xs text-accent"
            aria-hidden="true"
          >
            {user.name.slice(0, 2).toUpperCase()}
          </span>
        </div>
      ) : null}
    </header>
  );
}
