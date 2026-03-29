export const locales = ['es', 'en', 'de', 'pt', 'fr'] as const;
export const defaultLocale = 'es' as const;
export type Locale = (typeof locales)[number];
