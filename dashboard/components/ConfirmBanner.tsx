'use client';

interface Props { status?: string; }

export function ConfirmBanner({ status }: Props) {
  if (!status) return null;
  if (status === 'ok') {
    return (
      <div className="bg-good text-white text-sm font-medium text-center py-3 px-4">
        ✓ Alert confirmed! You&apos;ll receive emails when new matching listings appear.
      </div>
    );
  }
  if (status === 'already') {
    return (
      <div className="bg-bg border-b border-line text-ink-2 text-sm text-center py-3 px-4">
        This alert is already confirmed.
      </div>
    );
  }
  return (
    <div className="bg-red-50 border-b border-red-200 text-red-700 text-sm text-center py-3 px-4">
      Confirmation link invalid or expired. Please sign up again.
    </div>
  );
}
