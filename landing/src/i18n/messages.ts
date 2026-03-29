import es from "../../messages/es.json";
import en from "../../messages/en.json";
import de from "../../messages/de.json";
import pt from "../../messages/pt.json";
import fr from "../../messages/fr.json";
import type { Locale } from "./config";

const messages: Record<Locale, typeof es> = { es, en, de, pt, fr };

export function getMessages(locale: Locale) {
  return messages[locale] ?? messages.es;
}
