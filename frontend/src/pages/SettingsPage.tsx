/**
 * SettingsPage — display and edit user settings.
 *
 * Only exposes MVP-supported controls.  Future settings (UK accent,
 * reveal_first, accent compare) are intentionally hidden until the practice
 * flow supports them.
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

interface Props {
  onBack: () => void;
  onFocusChange: (focusPhonemes: string[]) => void;
  onStartPractice: (session: TodayResponse) => void;
}

const COMMON_FOCUS = ["/ʃ/", "/θ/", "/æ/", "/ɪ/", "/tʃ/", "/ʌ/"];

function canonicalFocus(phonemes: string[]): string[] {
  return Array.from(new Set(phonemes.map((item) => item.trim()).filter(Boolean))).sort();
}

export default function SettingsPage({
  onBack,
  onFocusChange,
  onStartPractice,
}: Props) {
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

  if (loading) return <main className="practice-container"><p>Loading…</p></main>;
  if (error) return <main className="practice-container"><p className="error">{error}</p></main>;
  if (!settings) return null;

  const update = async (patch: Partial<SettingsData>) => {
    setError(null);
    setSaved(false);
    try {
      const updated = await saveSettings(patch);
      setSettings(updated);
      setFocusInput(updated.focus_phonemes.join(", "));
      onFocusChange(updated.focus_phonemes);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save settings");
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
      setError(e instanceof Error ? e.message : "Failed to start focused practice");
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
        setError(e instanceof Error ? e.message : "Failed to clear focus");
      });
  };

  return (
    <main className="practice-container">
      <div className="page-header">
        <button className="back-btn" onClick={onBack}>← Today</button>
        <h1>Settings</h1>
      </div>

      {saved && <p className="save-confirm">✅ Saved</p>}
      {error && <p className="save-error">⚠️ {error}</p>}

      <div className="settings-form">
        {/* ---- MVP-supported controls ---- */}

        <label className="setting-row">
          <span>Words per group</span>
          <input type="number" min={1} max={50} value={settings.daily_word_count}
            onChange={e => update({ daily_word_count: Number(e.target.value) })} />
        </label>

        <label className="setting-row">
          <span>Show translation</span>
          <input type="checkbox" checked={settings.show_translation}
            onChange={e => update({ show_translation: e.target.checked })} />
        </label>

        <label className="setting-row">
          <span>Review strength</span>
          <select value={settings.review_strength}
            onChange={e => update({ review_strength: e.target.value })}>
            <option value="quick">Quick</option>
            <option value="normal">Normal</option>
            <option value="extra_review">Extra review</option>
          </select>
        </label>

        <section className="settings-panel">
          <h2>Focus practice</h2>
          <p className="section-copy">
            Pick a sound to start a focused group. The scheduler will weight words
            toward that sound until you clear focus.
          </p>
          <div className="phoneme-chip-list">
            {COMMON_FOCUS.map((phoneme) => (
              <button
                className="phoneme-chip selectable"
                key={phoneme}
                onClick={() => void startFocus(phoneme)}
                type="button"
              >
                Focus {phoneme}
              </button>
            ))}
          </div>
        </section>

        <details className="advanced-focus">
          <summary>Advanced/debug: manual IPA focus entry</summary>
          <label className="setting-row setting-row-stacked">
            <span>Comma-separated IPA symbols</span>
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
            <span className="focus-panel-label">Next group focus</span>
            <div className="phoneme-chip-list">
              {settings.focus_phonemes.map((phoneme) => (
                <button
                  className="phoneme-chip removable"
                  key={phoneme}
                  onClick={() => removeFocusPhoneme(phoneme)}
                  type="button"
                >
                  {phoneme} ×
                </button>
              ))}
            </div>
            <button
              className="secondary-action-btn compact"
              onClick={clearFocusPhonemes}
              type="button"
            >
              Clear focus
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
        <label className="setting-row">
          <span>Show accent compare</span>
          <input type="checkbox" checked={settings.show_accent_compare} … />
        </label>
        ---- */}
      </div>
    </main>
  );
}
