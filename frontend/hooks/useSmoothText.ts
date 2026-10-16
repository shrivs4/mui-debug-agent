'use client';

import { useState, useEffect, useRef } from 'react';

export function useSmoothText(target: string, isStreaming: boolean): string {
  const prefersReduced = useRef(
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  // For history messages (isStreaming=false on mount) or reduced-motion, start at full length
  // so there's nothing to animate.
  const initialLen = isStreaming && !prefersReduced.current ? 0 : target.length;
  const displayedLenRef = useRef(initialLen);
  const [displayedLen, setDisplayedLen] = useState(initialLen);

  // Keep mutable refs in sync with latest props so the rAF callback always
  // sees the current values without needing to re-subscribe to the effect.
  const targetRef = useRef(target);
  const isStreamingRef = useRef(isStreaming);
  useEffect(() => { targetRef.current = target; }, [target]);
  useEffect(() => { isStreamingRef.current = isStreaming; }, [isStreaming]);

  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // Skip animation entirely for history messages and reduced-motion users.
    if (prefersReduced.current || !isStreamingRef.current) return;

    const tick = () => {
      const t = targetRef.current;
      const streaming = isStreamingRef.current;
      const backlog = t.length - displayedLenRef.current;

      if (backlog > 0) {
        // While streaming: reveal at most ceil(backlog/30) chars per frame,
        // keeping the display ≤ ~500 ms (30 frames at 60 fps) behind the buffer.
        // After streaming ends: accelerate to ceil(backlog/18) to finish in ≤ 300 ms.
        const charsPerFrame = streaming
          ? Math.max(1, Math.ceil(backlog / 30))
          : Math.max(1, Math.ceil(backlog / 18));
        displayedLenRef.current = Math.min(t.length, displayedLenRef.current + charsPerFrame);
        setDisplayedLen(displayedLenRef.current);
      }

      // Keep looping while there's still backlog or more text may arrive.
      if (displayedLenRef.current < t.length || streaming) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        rafRef.current = null;
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []); // intentionally stable — tick reads latest values through refs

  if (prefersReduced.current) return target;
  return target.slice(0, displayedLen);
}
