import type { LucideIcon } from 'lucide-react';
import {
  Building2,
  CalendarDays,
  ClipboardList,
  FileSpreadsheet,
  HandCoins,
  LayoutDashboard,
  Settings,
  Table2,
  Users,
} from 'lucide-react';

export interface NavItem {
  href: string;
  /** Key under the `nav` namespace in messages/*.json */
  labelKey: string;
  icon: LucideIcon;
  /** Only company admins (and platform admins) see it. */
  adminOnly?: boolean;
  platformOnly?: boolean;
}

export const COMPANY_NAV: NavItem[] = [
  { href: '/dashboard', labelKey: 'dashboard', icon: LayoutDashboard },
  { href: '/daily-entry', labelKey: 'dailyEntry', icon: CalendarDays },
  { href: '/employees', labelKey: 'employees', icon: Users },
  { href: '/adjustments', labelKey: 'adjustments', icon: ClipboardList, adminOnly: true },
  { href: '/loans', labelKey: 'loans', icon: HandCoins, adminOnly: true },
  { href: '/payroll', labelKey: 'payroll', icon: Table2, adminOnly: true },
  { href: '/reports', labelKey: 'reports', icon: FileSpreadsheet, adminOnly: true },
  { href: '/settings', labelKey: 'settings', icon: Settings, adminOnly: true },
];

export const PLATFORM_NAV: NavItem[] = [
  { href: '/platform', labelKey: 'platform', icon: Building2, platformOnly: true },
];
