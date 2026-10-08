import { useEffect, useRef, useState } from "react";
import { checkAttention } from "../api/sessions";

// Matches attention_check_interval_seconds on the backend, which also decides
// how many seconds each recorded episode is worth.
const DEFAULT_INTERVAL_MS = 4000;
const MAX_REQUEST_FAILURES = 3;

/**
 * Live gaze readout while an interview is running. Runs more often than the
 * identity checks and never affects the identity verdict; sends nothing while
 * the camera is off.
 */
export default function useAttentionChecks({ sessionId, camera, active, intervalMs = DEFAULT_INTERVAL_MS }) {
  const [attention, setAttention] = useState(null);
  const [paused, setPaused] = useState(false);

  const cameraRef = useRef(camera);
  useEffect(() => {
    cameraRef.current = camera;
  });

  useEffect(() => {
    if (!active || !sessionId) return undefined;

    let stopped = false;
    let inFlight = false;
    let failures = 0;

    const tick = async () => {
      const cam = cameraRef.current;
      if (stopped || inFlight || !cam.enabled) return;
      inFlight = true;
      try {
        const frame = await cam.captureStill();
        if (!frame || stopped) return;
        const result = await checkAttention(sessionId, frame);
        if (stopped) return;
        failures = 0;
        setPaused(false);
        setAttention({ ...result.attention, state: result.state, label: result.label });
      } catch (err) {
        const status = err.response?.status;
        // Session ended, or attention tracking is switched off server-side.
        if (status === 409 || status === 404) {
          stopped = true;
          setPaused(true);
          return;
        }
        failures += 1;
        if (failures >= MAX_REQUEST_FAILURES) setPaused(true);
      } finally {
        inFlight = false;
      }
    };

    const timer = setInterval(tick, intervalMs);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [active, sessionId, intervalMs]);

  return { attention, paused };
}
