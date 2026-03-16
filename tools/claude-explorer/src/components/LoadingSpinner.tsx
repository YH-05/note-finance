/**
 * Simple loading spinner component.
 *
 * Displays a centered spinner with an optional message, used during
 * search debounce delays and initial data loading.
 */

interface LoadingSpinnerProps {
  /** Optional message to display below the spinner. */
  message?: string;
}

export function LoadingSpinner({ message }: LoadingSpinnerProps) {
  return (
    <div className="flex items-center justify-center h-32">
      <div className="text-center">
        <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
        {message && (
          <p className="text-sm text-gray-500 mt-2">{message}</p>
        )}
      </div>
    </div>
  );
}
