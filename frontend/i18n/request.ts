import { getRequestConfig } from 'next-intl/server';

export default getRequestConfig(async ({ requestLocale }) => {
  // requestLocale may be a Promise in some next-intl versions; await it
  let locale = typeof requestLocale?.then === 'function'
    ? await requestLocale
    : requestLocale;
  locale = locale ?? 'zh';

  const messages = (await import(`../messages/${locale}.json`)).default;

  return {
    locale,
    messages,
  };
});
