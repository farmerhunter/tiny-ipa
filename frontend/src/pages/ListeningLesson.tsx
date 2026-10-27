import { useEffect, useRef, useState } from "react";
import { fetchListening, listeningCommand, type ListeningLesson as Lesson } from "../api";
import { createTranslator, type Locale } from "../locales";

export default function ListeningLesson({ uiLanguage, onBack }: { uiLanguage: Locale; onBack: () => void }) {
  const t = createTranslator(uiLanguage);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [busy, setBusy] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const media = useRef<HTMLAudioElement | null>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    fetchListening().then(({ lesson: saved }) => saved ?? listeningCommand())
      .then((saved) => { if (alive.current) setLesson(saved); })
      .catch(() => { if (alive.current) setError(t("listening.error")); })
      .finally(() => { if (alive.current) setBusy(false); });
    return () => { alive.current = false; if (media.current) { media.current.onended = null; media.current.onerror = null; media.current.pause(); } };
    // The locale changes labels without restarting the saved lesson.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const command = async (action: string, selectedAnswer?: string) => {
    if (!lesson || busy) return;
    setBusy(true); setError(null);
    try {
      const saved = await listeningCommand(lesson.id, { action, index: lesson.cursor, selected_answer: selectedAnswer });
      if (alive.current) setLesson(saved);
    } catch { if (alive.current) setError(t("listening.error")); }
    finally { if (alive.current) setBusy(false); }
  };
  const play = (url: string, scored = false) => {
    if (playing || busy) return;
    if (media.current) { media.current.onended = null; media.current.onerror = null; media.current.pause(); }
    const audio = new Audio(url); media.current = audio; setPlaying(true); setError(null);
    const failed = () => { if (alive.current) { setPlaying(false); setError(t("listening.audio_error")); } };
    audio.onerror = failed;
    audio.onended = () => { if (alive.current) { setPlaying(false); if (scored) void command("played"); } };
    void audio.play().catch(failed);
  };
  const restart = async () => {
    if (busy) return;
    setBusy(true); setError(null);
    try { setLesson(await listeningCommand()); }
    catch { setError(t("listening.error")); }
    finally { setBusy(false); }
  };
  const item = lesson?.item;
  return <main className="practice-container listening-preview">
    <button className="btn-secondary" onClick={onBack}>{t("app.back.today")}</button>
    <h1>{t("listening.title")}</h1>
    <p>{t("listening.notice")}</p>
    {error && <p role="alert">{error}</p>}
    {!lesson && <p>{busy ? t("action.loading") : t("listening.error")}</p>}
    {lesson?.phase === "demo" && <section>
      <h2>{t("listening.demo")}</h2>
      <p>{t("listening.contrast")}</p>
      {lesson.demo.map((word) => <p key={word.word}>{word.word} {word.ipa} <button disabled={busy || playing} onClick={() => play(word.audio_url)}>{t("listening.play_word", { word: word.word })}</button></p>)}
      <button disabled={busy || playing} className="btn-primary" onClick={() => void command("begin")}>{t("listening.begin")}</button>
    </section>}
    {lesson?.phase === "question" && item && <section>
      <h2>{t("listening.item", { n: lesson.cursor + 1 })}</h2>
      <p>{t(lesson.cursor < 4 ? "listening.practice" : "listening.new_words")}</p>
      <button className="btn-primary" disabled={busy || playing} onClick={() => play(item.audio_url, true)}>{t("listening.play")}</button>
      <p aria-live="polite">{t(playing ? "listening.playing" : item.heard ? "listening.choose" : "listening.hear_first")}</p>
      <div className="choices-list">{item.choices.map((choice) => <button key={choice} className="choice-btn" disabled={busy || playing || !item.heard || Boolean(item.feedback)} onClick={() => void command("answer", choice)}>{choice}</button>)}</div>
      {item.feedback && <div className="feedback" role="status">
        <p>{t(item.feedback.is_correct ? "listening.correct" : "listening.wrong", { word: item.feedback.correct })}</p>
        <button disabled={busy || playing} onClick={() => void command("next")}>{t("listening.next")}</button>
      </div>}
    </section>}
    {lesson?.phase === "completed" && <section>
      <h2>{t("listening.complete")}</h2>
      <p data-testid="listening-score">{t("listening.score", { n: lesson.summary.correct })}</p>
      <p>{t("listening.parts", { practice: lesson.summary.practice_correct, check: lesson.summary.new_words_correct })}</p>
      <h3>{t("listening.review")}</h3>
      {lesson.answers.filter((answer) => !answer.is_correct).map((answer) => <p key={answer.index}>{answer.selected} → {answer.correct} <button disabled={playing || busy} onClick={() => play(answer.audio_url)}>{t("listening.play_word", { word: answer.correct })}</button></p>)}
      <button disabled={busy || playing} onClick={() => void restart()}>{t("listening.again")}</button>
    </section>}
  </main>;
}
