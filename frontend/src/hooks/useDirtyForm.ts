import { useState, useCallback, useMemo, useRef } from 'react';

/**
 * Normalize a value for comparison:
 * - Strings are trimmed
 * - null / undefined become ''
 * - Everything else is left as-is
 */
function normalize(value: unknown): unknown {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value.trim();
  return value;
}

/**
 * Deep-equal comparison of two plain objects after normalizing every leaf value.
 */
function isDeepEqual<T extends Record<string, unknown>>(a: T, b: T): boolean {
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);

  if (keysA.length !== keysB.length) return false;

  return keysA.every((key) => {
    const valA = normalize(a[key]);
    const valB = normalize(b[key]);

    // Handle nested objects (one level deep is enough for our forms)
    if (
      typeof valA === 'object' &&
      valA !== null &&
      typeof valB === 'object' &&
      valB !== null
    ) {
      return isDeepEqual(
        valA as Record<string, unknown>,
        valB as Record<string, unknown>,
      );
    }

    return valA === valB;
  });
}

/**
 * Generic dirty-state hook for forms.
 *
 * Usage:
 * ```ts
 * const { formData, setFormData, isDirty, resetOriginal, handleChange } =
 *   useDirtyForm({ username: 'alice', bio: '' });
 * ```
 *
 * `isDirty` is `true` whenever the current `formData` differs from the
 * snapshot stored at creation time (or since the last `resetOriginal` call).
 */
export function useDirtyForm<T extends Record<string, any>>(initialValues: T) {
  const originalRef = useRef<T>(initialValues);
  const [formData, setFormData] = useState<T>(initialValues);

  const isDirty = useMemo(
    () => !isDeepEqual(formData as Record<string, unknown>, originalRef.current as Record<string, unknown>),
    [formData],
  );

  /**
   * Update the "original" baseline.
   * Call this after a successful save, or when the source data refreshes.
   * If `newValues` is provided the form state is also reset to those values.
   */
  const resetOriginal = useCallback((newValues?: T) => {
    if (newValues !== undefined) {
      originalRef.current = newValues;
      setFormData(newValues);
    } else {
      // Snapshot the current formData as the new baseline
      originalRef.current = formData;
    }
  }, [formData]);

  /** Convenience handler for native `<input>` / `<textarea>` elements. */
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const { name, value } = e.target;
      setFormData((prev) => ({ ...prev, [name]: value }));
    },
    [],
  );

  return { formData, setFormData, isDirty, resetOriginal, handleChange } as const;
}
