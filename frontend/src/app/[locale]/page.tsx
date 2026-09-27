import { redirect } from '@/i18n/navigation';

/** The app has no marketing page: signed-in users belong on the dashboard. */
export default async function IndexPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  redirect({ href: '/dashboard', locale });
}
