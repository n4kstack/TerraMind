import { useCallback, useRef, useState } from 'react';
import { ApiError } from '@/lib/api';

export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error';

interface AsyncState<T> {
  status: AsyncStatus;
  data: T | null;
  error: string | null;
  isOffline: boolean;
}

/**
 * One request lifecycle, shared by every module page.
 *
 * Two things it guarantees that ad-hoc useState triples did not:
 *  - Out-of-order responses cannot overwrite newer ones. Each run takes a
 *    sequence number and stale resolutions are discarded, so double-submitting
 *    can't leave the older result on screen.
 *  - Errors are normalised to a message plus an `isOffline` flag, so the UI can
 *    distinguish "no connection" from "the server rejected this".
 */
export function useAsyncAction<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
) {
  const [state, setState] = useState<AsyncState<TResult>>({
    status: 'idle',
    data: null,
    error: null,
    isOffline: false,
  });

  const runId = useRef(0);

  const run = useCallback(
    async (...args: TArgs) => {
      const id = ++runId.current;
      setState({ status: 'loading', data: null, error: null, isOffline: false });

      try {
        const data = await fn(...args);
        if (id !== runId.current) return;
        setState({ status: 'success', data, error: null, isOffline: false });
        return data;
      } catch (error) {
        if (id !== runId.current) return;
        const isApi = error instanceof ApiError;
        setState({
          status: 'error',
          data: null,
          error: isApi ? error.message : 'An unexpected error occurred. Please try again.',
          isOffline: isApi ? error.isOffline : false,
        });
        return undefined;
      }
    },
    [fn],
  );

  const reset = useCallback(() => {
    runId.current += 1;
    setState({ status: 'idle', data: null, error: null, isOffline: false });
  }, []);

  return { ...state, run, reset };
}
