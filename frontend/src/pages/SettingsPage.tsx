/**
 * SettingsPage — display and edit user settings.
 */

import { useEffect, useState } from "react";

interface SettingsData {
  primary_accent: string;
  daily_word_count: number;
  show_translation: boolean;
  show_accent_compare: boolean;
  practice_mode: string;
  review_strength: string;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function fetchSettings(): Promise<SettingsData> {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) throw new Error("Failed to load settings");
  return res.json();
}

async function saveSettings(data: Partial<SettingsData>): Promise<SettingsData> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const inner = body.detail ?? body;
    throw new Error(typeof inner === "string" ? inner : inner.detail ?? "Save failed");
  }
  return res.json();
}

interface Props {
  onBack: () => void;
}

export default function SettingsPage({ onBack }: Props) {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchSettings().then(setSettings).catch(e => setError(e.message)).finally(() => setLoading(false));
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
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e.message);
    }
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
        <label className="setting-row">
          <span>Words per day</span>
          <input type="number" min={1} max={50} value={settings.daily_word_count}
            onChange={e => update({ daily_word_count: Number(e.target.value) })} />
        </label>

        <label className="setting-row">
          <span>Primary accent</span>
          <select value={settings.primary_accent}
            onChange={e => update({ primary_accent: e.target.value })}>
            <option value="US">US</option>
            <option value="UK">UK</option>
          </select>
        </label>

        <label className="setting-row">
          <span>Practice mode</span>
          <select value={settings.practice_mode}
            onChange={e => update({ practice_mode: e.target.value })}>
            <option value="ipa_first">IPA first</option>
            <option value="reveal_first">Reveal first</option>
          </select>
        </label>

        <label className="setting-row">
          <span>Review strength</span>
          <select value={settings.review_strength}
            onChange={e => update({ review_strength: e.target.value })}>
            <option value="normal">Normal</option>
            <option value="extra_review">Extra review</option>
            <option value="quick">Quick</option>
          </select>
        </label>

        <label className="setting-row">
          <span>Show translation</span>
          <input type="checkbox" checked={settings.show_translation}
            onChange={e => update({ show_translation: e.target.checked })} />
        </label>

        <label className="setting-row">
          <span>Show accent compare</span>
          <input type="checkbox" checked={settings.show_accent_compare}
            onChange={e => update({ show_accent_compare: e.target.checked })} />
        </label>
      </div>
    </main>
  );
}
