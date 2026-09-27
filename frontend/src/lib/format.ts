/**
 * Money and number formatting.
 *
 * The API sends money as strings to avoid float rounding; `decimal.js` does any
 * client-side arithmetic, and `Intl.NumberFormat` renders it. Digits default to
 * Latin even in Arabic, which is what payroll staff expect on a keypad — the
 * `arabicDigits` flag switches to Arabic-Indic when a company prefers it.
 */
import Decimal from 'decimal.js';

export type Locale = 'ar' | 'en';

Decimal.set({ precision: 28, rounding: Decimal.ROUND_HALF_UP });

export function toDecimal(value: string | number | null | undefined): Decimal {
  if (value === null || value === undefined || value === '') return new Decimal(0);
  try {
    return new Decimal(value);
  } catch {
    return new Decimal(0);
  }
}

/** Sum a column of API money strings without ever touching a float. */
export function sumMoney(values: Array<string | number | null | undefined>): string {
  return values.reduce<Decimal>((total, v) => total.plus(toDecimal(v)), new Decimal(0)).toFixed(2);
}

function numberLocale(locale: Locale, arabicDigits: boolean): string {
  if (locale !== 'ar') return 'en-US';
  return arabicDigits ? 'ar-EG' : 'ar-EG-u-nu-latn';
}

export function formatMoney(
  value: string | number | null | undefined,
  locale: Locale = 'ar',
  options: { arabicDigits?: boolean } = {},
): string {
  const amount = toDecimal(value).toDecimalPlaces(2, Decimal.ROUND_HALF_UP).toNumber();
  return new Intl.NumberFormat(numberLocale(locale, options.arabicDigits ?? false), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatQuantity(
  value: string | number | null | undefined,
  locale: Locale = 'ar',
  options: { arabicDigits?: boolean } = {},
): string {
  const amount = toDecimal(value).toNumber();
  return new Intl.NumberFormat(numberLocale(locale, options.arabicDigits ?? false), {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatPercent(value: number, locale: Locale = 'ar'): string {
  return new Intl.NumberFormat(numberLocale(locale, false), {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatDate(value: string | Date | null | undefined, locale: Locale = 'ar'): string {
  if (!value) return '—';
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(locale === 'ar' ? 'ar-EG-u-nu-latn-ca-gregory' : 'en-GB', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  }).format(date);
}

export function formatDateTime(
  value: string | Date | null | undefined,
  locale: Locale = 'ar',
): string {
  if (!value) return '—';
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(locale === 'ar' ? 'ar-EG-u-nu-latn-ca-gregory' : 'en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

/** `2026-02-09` — the format every API date field expects. */
export function isoDate(date: Date): string {
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

export const ARABIC_MONTHS = [
  'يناير',
  'فبراير',
  'مارس',
  'ابريل',
  'مايو',
  'يونيو',
  'يوليو',
  'اغسطس',
  'سبتمبر',
  'اكتوبر',
  'نوفمبر',
  'ديسمبر',
];

export const ENGLISH_MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

export function monthName(month: number, locale: Locale = 'ar'): string {
  const names = locale === 'ar' ? ARABIC_MONTHS : ENGLISH_MONTHS;
  return names[month - 1] ?? String(month);
}
