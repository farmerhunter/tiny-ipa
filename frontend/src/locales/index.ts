import enUS from "./en-US.json";
import zhCN from "./zh-CN.json";

export const DEFAULT_LOCALE = "zh-CN";
export const FALLBACK_LOCALE = "en-US";

export const SUPPORTED_LOCALES = ["zh-CN", "en-US"] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];
export type LocaleKey = keyof typeof zhCN;
export type LocaleValues = Record<string, string | number>;
export type Translator = ReturnType<typeof createTranslator>;

export type MissingKeyEvent = {
  locale: Locale;
  key: string;
  fallbackLocale: Locale;
  usedFallback: boolean;
};

export type TranslatorOptions = {
  environment?: "development" | "test" | "production";
  onMissingKey?: (event: MissingKeyEvent) => void;
};

export const localeResources: Record<Locale, Record<LocaleKey, string>> = {
  "zh-CN": zhCN,
  "en-US": enUS,
};

export function isSupportedLocale(locale: string | null | undefined): locale is Locale {
  return SUPPORTED_LOCALES.includes(locale as Locale);
}

export function resolveLocale(locale: string | null | undefined): Locale {
  return isSupportedLocale(locale) ? locale : DEFAULT_LOCALE;
}

export function createTranslator(
  requestedLocale: string | null | undefined,
  options: TranslatorOptions = {},
) {
  const locale = resolveLocale(requestedLocale);
  const environment = options.environment ?? import.meta.env.MODE;

  return (key: LocaleKey | string, values: LocaleValues = {}) => {
    const text = localeResources[locale][key as LocaleKey];
    if (text !== undefined) {
      return interpolate(text, values);
    }

    const fallback = localeResources[FALLBACK_LOCALE][key as LocaleKey];
    const useFallback = environment === "production" && fallback !== undefined;
    options.onMissingKey?.({
      locale,
      key,
      fallbackLocale: FALLBACK_LOCALE,
      usedFallback: useFallback,
    });

    if (useFallback) {
      return interpolate(fallback, values);
    }

    return `⟦missing:${locale}:${key}⟧`;
  };
}

function interpolate(text: string, values: LocaleValues): string {
  return text.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g, (match, name: string) => {
    const value = values[name];
    return value === undefined ? match : String(value);
  });
}
