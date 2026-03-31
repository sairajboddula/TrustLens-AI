import { cn } from '@/utils/cn';

type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface SpinnerProps {
  size?:      SpinnerSize;
  color?:     'primary' | 'white' | 'gray';
  className?: string;
  label?:     string;
}

const sizeMap: Record<SpinnerSize, string> = {
  xs: 'h-3 w-3 border-[1.5px]',
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-8 w-8 border-[3px]',
  xl: 'h-12 w-12 border-4',
};

const colorMap = {
  primary: 'border-primary-200 border-t-primary-600',
  white:   'border-white/30   border-t-white',
  gray:    'border-neutral-200 border-t-neutral-500',
};

export function Spinner({ size = 'md', color = 'primary', className, label }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label={label ?? 'Loading…'}
      className={cn('inline-block rounded-full animate-spin', sizeMap[size], colorMap[color], className)}
    />
  );
}

// ─── Full-page / overlay spinner ─────────────────────────────────────────────

interface LoadingScreenProps {
  message?: string;
}

export function LoadingScreen({ message = 'Loading…' }: LoadingScreenProps) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm">
      <Spinner size="xl" />
      <p className="mt-4 text-sm text-neutral-500 font-medium">{message}</p>
    </div>
  );
}

// ─── Inline loading state ─────────────────────────────────────────────────────

export function LoadingState({ message = 'Loading…' }: LoadingScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <Spinner size="lg" />
      <p className="text-sm text-neutral-500">{message}</p>
    </div>
  );
}
