import { reactive } from 'vue';
import en from './en.json';
import pt from './pt.json';

type Messages = typeof pt;
type Locale = 'en' | 'pt';

const messages: Record<Locale, Messages> = { en, pt };

const state = reactive<{ locale: Locale; messages: Messages }>({
  locale: 'pt',
  messages: messages['pt'],
});

export function t(key: keyof Messages): string {
  return state.messages[key] ?? key;
}

export function setLocale(locale: Locale): void {
  state.locale = locale;
  state.messages = messages[locale];
}

export function getLocale(): Locale {
  return state.locale;
}

export { state as i18nState };
