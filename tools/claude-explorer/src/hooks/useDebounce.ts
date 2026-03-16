/**
 * Generic debounce hook.
 *
 * Returns the debounced value after the specified delay.
 */
import { useEffect, useRef, useState } from "react";

export function useDebounce<T>(value: T, delay: number): { debouncedValue: T; isPending: boolean } {
  const [debouncedValue, setDebouncedValue] = useState(value);
  const [isPending, setIsPending] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (value !== debouncedValue) {
      setIsPending(true);
    }

    timerRef.current = setTimeout(() => {
      setDebouncedValue(value);
      setIsPending(false);
    }, delay);

    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, [value, delay]); // eslint-disable-line react-hooks/exhaustive-deps

  return { debouncedValue, isPending };
}
