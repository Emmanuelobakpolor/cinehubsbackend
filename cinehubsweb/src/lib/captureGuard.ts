import { useEffect, useState } from 'react';

/**
 * Best-effort screenshot / screen-recording deterrent for the player.
 *
 * A web page cannot detect or stop OS-level capture. When a movie plays in
 * "drm" mode (see lib/streaming.ts) the browser/OS may itself black out the
 * video in captures — reliably on Safari/iOS with FairPlay and on hardware-backed
 * Widevine/PlayReady, rarely on desktop Chrome's software Widevine — while the
 * free AES-128 "hls" mode gets no such protection. So this stays as a secondary
 * layer for every mode: it hides the picture whenever capture is likely — the
 * window loses focus (Snipping Tool, OBS, Game Bar overlays steal it), the tab
 * is hidden, or a screenshot shortcut is pressed. Recording tools that never
 * take focus are not caught; the viewer watermark is what traces those leaks.
 */
export function useCaptureGuard(onShield: () => void) {
  const [shielded, setShielded] = useState(false);

  useEffect(() => {
    const shield = () => {
      setShielded(true);
      onShield();
    };
    // Screenshot keys can fire after the OS grabs the frame, so also wipe the clipboard copy.
    const flash = () => {
      shield();
      navigator.clipboard?.writeText('').catch(() => {});
    };

    const onKey = (e: KeyboardEvent) => {
      const k = (e.key || '').toLowerCase();
      const winSnip = e.metaKey && e.shiftKey && k === 's'; // Win+Shift+S
      const macShot = e.metaKey && e.shiftKey && ['3', '4', '5', '6'].includes(k); // Cmd+Shift+3/4/5/6
      const gameBar = e.metaKey && e.altKey && (k === 'r' || k === 'printscreen'); // Win+Alt+R
      if (k === 'printscreen' || winSnip || macShot || gameBar) {
        e.preventDefault();
        flash();
      } else if (e.ctrlKey && (k === 'p' || k === 's')) {
        e.preventDefault(); // print / save page
      }
    };
    const onBlur = () => shield();
    const onVisibility = () => document.visibilityState === 'hidden' && shield();
    const block = (e: Event) => e.preventDefault();

    window.addEventListener('keydown', onKey, true);
    window.addEventListener('keyup', onKey, true); // PrintScreen only reports keyup on Windows
    window.addEventListener('blur', onBlur);
    document.addEventListener('visibilitychange', onVisibility);
    document.addEventListener('contextmenu', block);
    document.addEventListener('dragstart', block);
    window.addEventListener('beforeprint', shield);
    return () => {
      window.removeEventListener('keydown', onKey, true);
      window.removeEventListener('keyup', onKey, true);
      window.removeEventListener('blur', onBlur);
      document.removeEventListener('visibilitychange', onVisibility);
      document.removeEventListener('contextmenu', block);
      document.removeEventListener('dragstart', block);
      window.removeEventListener('beforeprint', shield);
    };
  }, [onShield]);

  return { shielded, unshield: () => setShielded(false) };
}
