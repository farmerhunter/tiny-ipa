/**
 * SettingsPage — display and edit user settings.
 *
 * Only exposes learner-supported controls. UK remains comparison-only in M9.
 */

import { useEffect, useState } from "react";
import {
  type SettingsData,
  type TodayResponse,
  clearPracticeFocus,
  fetchSettings,
  saveSettings,
  startFocusedPractice,
} from "../api";
import { createTranslator, type Locale } from "../locales";

interface Props {
  uiLanguage: Locale;
  onBack: () => void;
  onLanguageChange: (locale: Locale) => void;
  onFocusChange: (focusPhonemes: string[]) => void;
  onStartPractice: (session: TodayResponse) => void;
}

const COMMON_FOCUS = ["/ʃ/", "/θ/", "/æ/", "/ɪ/", "/tʃ/", "/ʌ/"];

const LEVEL_OPTIONS: Array<{
  value: SettingsData["learner_level"];
  titleKey: "settings.level.entry.title" | "settings.level.mid.title";
  descriptionKey: "settings.level.entry.description" | "settings.level.mid.description";
}> = [
  {
    value: "entry",
    titleKey: "settings.level.entry.title",
    descriptionKey: "settings.level.entry.description",
  },
  {
    value: "mid",
    titleKey: "settings.level.mid.title",
    descriptionKey: "settings.level.mid.description",
  },
];

const UI_LANGUAGE_OPTIONS: Array<{
  value: SettingsData["ui_language"];
  labelKey: "settings.ui_language.zh_cn" | "settings.ui_language.en_us";
}> = [
  { value: "zh-CN", labelKey: "settings.ui_language.zh_cn" },
  { value: "en-US", labelKey: "settings.ui_language.en_us" },
];

function canonicalFocus(phonemes: string[]): string[] {
  return Array.from(new Set(phonemes.map((item) => item.trim()).filter(Boolean))).sort();
}

export default function SettingsPage({
  uiLanguage,
  onBack,
  onLanguageChange,
  onFocusChange,
  onStartPractice,
}: Props) {
  const t = createTranslator(uiLanguage);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [focusInput, setFocusInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then((data) => {
        setSettings(data);
        setFocusInput(data.focus_phonemes.join(", "));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main className="practice-container"><p>{t("settings.loading")}</p></main>;
  if (error) return <main className="practice-container"><p className="error">{error}</p></main>;
  if (!settings) return null;

  const update = async (patch: Partial<SettingsData>) => {
    setError(null);
    setSaved(false);
    try {
      const updated = await saveSettings(patch);
      setSettings(updated);
      setFocusInput(updated.focus_phonemes.join(", "));
      onLanguageChange(updated.ui_language);
      onFocusChange(updated.focus_phonemes);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("error.settings.save_failed"));
    }
  };

  const saveFocusPhonemes = () => {
    const focus_phonemes = canonicalFocus(focusInput.split(","));
    void update({ focus_phonemes });
  };

  const startFocus = async (phoneme: string) => {
    setError(null);
    setSaved(false);
    try {
      const session = await startFocusedPractice([phoneme]);
      const appliedFocus = session.focus_phonemes ?? [phoneme];
      setSettings({ ...settings, focus_phonemes: appliedFocus });
      setFocusInput(appliedFocus.join(", "));
      onFocusChange(appliedFocus);
      onStartPractice(session);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("error.practice.focus_start_failed"));
    }
  };

  const removeFocusPhoneme = (phoneme: string) => {
    void update({
      focus_phonemes: settings.focus_phonemes.filter((item) => item !== phoneme),
    });
  };

  const clearFocusPhonemes = () => {
    clearPracticeFocus()
      .then((session) => {
        setSettings({ ...settings, focus_phonemes: [] });
        setFocusInput("");
        onFocusChange([]);
        onStartPractice(session);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : t("error.practice.clear_focus_failed"));
      });
  };

  return (
    <main className="practice-container">
      <div className="page-header">
        <button className="back-btn" onClick={onBack}>{t("app.back.today")}</button>
        <h1>{t("app.nav.settings")}</h1>
      </div>

      {saved && <p className="save-confirm">{t("settings.saved")}</p>}
      {error && <p className="save-error">{error}</p>}

      <div className="settings-form">
        {/* ---- MVP-supported controls ---- */}

        <label className="setting-row">
          <span>{t("settings.words_per_group")}</span>
          <input type="number" min={1} max={50} value={settings.daily_word_count}
            onChange={e => update({ daily_word_count: Number(e.target.value) })} />
        </label>

        <label className="setting-row">
          <span>{t("settings.show_translation")}</span>
          <input type="checkbox" checked={settings.show_translation}
            onChange={e => update({ show_translation: e.target.checked })} />
        </label>

        <label className="setting-row">
          <span>
            {t("settings.accent_compare.title")}
            <small>{t("settings.accent_compare.description")}</small>
          </span>
          <input type="checkbox" checked={settings.show_accent_compare}
            onChange={e => update({ show_accent_compare: e.target.checked })} />
        </label>

        <label className="setting-row">
          <span>
            {t("settings.review_strength.title")}
            <small>{t("settings.review_strength.description")}</small>
          </span>
          <select value={settings.review_strength}
            onChange={e => update({ review_strength: e.target.value })}>
            <option value="quick">{t("settings.review_strength.quick")}</option>
            <option value="normal">{t("settings.review_strength.normal")}</option>
            <option value="extra_review">{t("settings.review_strength.extra_review")}</option>
          </select>
        </label>

        <label className="setting-row">
          <span>{t("settings.ui_language.title")}</span>
          <select value={settings.ui_language}
            onChange={e => update({ ui_language: e.target.value as SettingsData["ui_language"] })}>
            {UI_LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{t(option.labelKey)}</option>
            ))}
          </select>
        </label>

        <section className="settings-panel">
          <div className="account-box">
            <div className="account-icon" aria-hidden="true">人</div>
            <div>
              <strong>{t("app.login.disabled.title")}</strong>
              <span>{t("app.login.disabled.details")}</span>
            </div>
          </div>

          <h2>{t("settings.practice_level.title")}</h2>
          <p className="section-copy">
            {t("settings.practice_level.description")}
          </p>
          <div className="level-choice-list">
            {LEVEL_OPTIONS.map((option) => (
              <button
                className={`level-choice ${settings.learner_level === option.value ? "selected" : ""}`}
                key={option.value}
                onClick={() => void update({ learner_level: option.value })}
                type="button"
              >
                <strong>{t(option.titleKey)}</strong>
                <span>{t(option.descriptionKey)}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="settings-panel">
          <h2>{t("settings.focus_practice.title")}</h2>
          <p className="section-copy">
            {t("settings.focus_practice.description")}
          </p>
          <div className="phoneme-chip-list">
            {COMMON_FOCUS.map((phoneme) => (
              <button
                className="phoneme-chip selectable"
                key={phoneme}
                onClick={() => void startFocus(phoneme)}
                type="button"
              >
                {t("focus.action.start_phoneme", { phoneme })}
              </button>
            ))}
          </div>
        </section>

        <details className="advanced-focus">
          <summary>{t("settings.focus.manual.title")}</summary>
          <label className="setting-row setting-row-stacked">
            <span>{t("settings.focus.manual.description")}</span>
            <input
              className="focus-input"
              type="text"
              value={focusInput}
              placeholder="/ʃ/, /æ/"
              onBlur={saveFocusPhonemes}
              onChange={e => setFocusInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter") {
                  e.currentTarget.blur();
                }
              }}
            />
          </label>
        </details>

        {settings.focus_phonemes.length > 0 && (
          <div className="settings-focus-panel">
            <span className="focus-panel-label">{t("focus.next.label")}</span>
            <div className="phoneme-chip-list">
              {settings.focus_phonemes.map((phoneme) => (
                <button
                  className="phoneme-chip removable"
                  key={phoneme}
                  onClick={() => removeFocusPhoneme(phoneme)}
                  type="button"
                >
                  {t("focus.action.remove", { phoneme })}
                </button>
              ))}
            </div>
            <button
              className="secondary-action-btn compact"
              onClick={clearFocusPhonemes}
              type="button"
            >
              {t("focus.action.clear_button")}
            </button>
          </div>
        )}

        {/* ---- Future controls (hidden until practice flow supports them) ----
        <label className="setting-row">
          <span>Primary accent</span>
          <select value={settings.primary_accent} … />
        </label>
        <label className="setting-row">
          <span>Practice mode</span>
          <select value={settings.practice_mode} … />
        </label>
        ---- */}
      </div>
    </main>
  );
}
