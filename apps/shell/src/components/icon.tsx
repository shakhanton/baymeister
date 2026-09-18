import {
  Bell,
  BookOpen,
  CalendarDays,
  Car,
  ClipboardList,
  FileText,
  HandCoins,
  LayoutDashboard,
  LineChart,
  Map,
  Package,
  Plug,
  SearchCheck,
  Truck,
  UserCog,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react';

/**
 * Іконки каркаса. Модуль вказує рядок у маніфесті, а не імпортує компонент —
 * інакше кожен блок тягнув би власну іконотеку.
 */
const ICONS: Record<string, LucideIcon> = {
  bell: Bell,
  'book-open': BookOpen,
  'calendar-days': CalendarDays,
  car: Car,
  'clipboard-list': ClipboardList,
  dashboard: LayoutDashboard,
  'file-text': FileText,
  'hand-coins': HandCoins,
  'line-chart': LineChart,
  map: Map,
  package: Package,
  plug: Plug,
  'search-check': SearchCheck,
  truck: Truck,
  'user-cog': UserCog,
  users: Users,
  wallet: Wallet,
};

export function Icon({ name, className }: { name: string; className?: string }) {
  const Component = ICONS[name] ?? LayoutDashboard;
  return <Component className={className} aria-hidden="true" />;
}
