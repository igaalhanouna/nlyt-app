import { useEffect, useCallback } from 'react';

/**
 * Saves scroll position before navigating away, restores it on return.
 * @param {string} pageKey - Unique key for the page (e.g. 'dashboard')
 * @param {boolean} ready - Set to true once data is loaded and rendered
 */
export function useScrollRestore(pageKey, ready = true) {
  useEffect(() => {
    if (!ready) return;
    const saved = sessionStorage.getItem(`scroll_${pageKey}`);
    if (saved) {
      const y = parseInt(saved, 10);
      // Double rAF ensures DOM is painted before scrolling
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          window.scrollTo({ top: y, behavior: 'instant' });
        });
      });
      sessionStorage.removeItem(`scroll_${pageKey}`);
    }
  }, [pageKey, ready]);

  const saveScroll = useCallback(() => {
    sessionStorage.setItem(`scroll_${pageKey}`, String(window.scrollY));
  }, [pageKey]);

  return { saveScroll };
}
