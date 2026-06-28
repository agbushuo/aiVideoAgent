import { NextIntlClientProvider } from 'next-intl';
import { useMessages } from 'next-intl';

export default function ClientProvider({ children, locale }: { children: React.ReactNode, locale: string }) {
  const messages = useMessages();
  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}
