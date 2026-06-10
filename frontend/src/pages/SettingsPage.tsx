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
  fetchSettings,
  saveSettings,
} from "../api";

interface Props {
  onBack: () => void;
}

export default function SettingsPage({ onBack }: Props) {
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
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save settings");
    }
  };

  const saveFocusPhonemes = () => {
    const focus_phonemes = focusInput
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    void update({ focus_phonemes });
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
          <span>Words per day</span>
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

        <label className="setting-row setting-row-stacked">
          <span>Focus phonemes</span>
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

        {settings.focus_phonemes.length > 0 && (
          <div className="phoneme-chip-list">
            {settings.focus_phonemes.map((phoneme) => (
              <span className="phoneme-chip" key={phoneme}>{phoneme}</span>
            ))}
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
