import { useEffect, useRef, useState } from "react";

/**
 * True once the element has entered the viewport. Used to drive the landing
 * page's scroll-reveal — it fires once and stays true, so scrolling back up
 * doesn't re-hide content that was already read.
 *
 * Content gated behind this must never depend on it firing: a backgrounded
 * tab, a browser that throttles IntersectionObserver, or any other edge case
 * that keeps it from ever firing would otherwise leave real content
 * permanently invisible. The fallback timer makes that failure mode
 * impossible — worst case, the reveal animation is skipped and the content
 * just appears.
 */
export default function useInView({ threshold = 0.15, fallbackMs = 2500 } = {}) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold }
    );
    observer.observe(el);

    const fallback = setTimeout(() => setInView(true), fallbackMs);

    return () => {
      observer.disconnect();
      clearTimeout(fallback);
    };
  }, [threshold, fallbackMs]);

  return [ref, inView];
}
