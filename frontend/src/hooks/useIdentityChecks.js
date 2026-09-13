import { useEffect, useRef, useState } from "react";
import { checkIdentity } from "../api/sessions";

// Consecutive failed requests (network, server) before checks pause. These
// never count against the candidate — only completed checks do.
const MAX_REQUEST_FAILURES = 3;

/**
 * Periodic identity checks while an interview is running.
 *
 * Sends one still every `identity.check_interval_seconds`; if the camera is
 * off it reports that instead of silently skipping, so turning the camera
 * off can't dodge the checks. Results flow back through `onIdentity`.
 */
export default function useIdentityChecks({ sessionId, identity, camera, active, onIdentity }) {
  const [lastCheck, setLastCheck] = useState(null);
  const [paused, setPaused] = useState(false);

  // Read through refs so the interval isn't torn down on every render.
  const cameraRef = useRef(camera);
  const onIdentityRef = useRef(onIdentity);
  useEffect(() => {
    cameraRef.current = camera;
    onIdentityRef.current = onIdentity;
  });

  const intervalMs = (identity?.check_interval_seconds ?? 15) * 1000;

  useEffect(() => {
    if (!active) return undefined;

    let stopped = false;
    let inFlight = false;
    let failures = 0;

    const tick = async () => {
      if (stopped || inFlight) return;
      inFlight = true;
      try {
        const cam = cameraRef.current;
        const frame = cam.enabled ? await cam.captureStill() : null;
        const result = await checkIdentity(sessionId, frame);
        if (stopped) return;
        failures = 0;
        setPaused(false);
        setLastCheck({ outcome: result.outcome, hint: result.hint, at: Date.now() });
        onIdentityRef.current(result.identity);
      } catch (err) {
        const status = err.response?.status;
        if (status === 429) return;
        // Session ended or its reference expired: nothing more to check.
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

  return { lastCheck, paused };
}
