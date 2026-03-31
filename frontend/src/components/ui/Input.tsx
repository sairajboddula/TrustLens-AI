import React from 'react';
import { cn } from '@/utils/cn';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?:       string;
  error?:       string;
  helperText?:  string;
  leftElement?: React.ReactNode;
  rightElement?: React.ReactNode;
  containerClassName?: string;
}

// ─── Component ────────────────────────────────────────────────────────────────

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      helperText,
      leftElement,
      rightElement,
      containerClassName,
      className,
      id,
      required,
      ...props
    },
    ref,
  ) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className={cn('flex flex-col gap-1.5', containerClassName)}>
        {label && (
          <label
            htmlFor={inputId}
            className="text-sm font-medium text-neutral-700"
          >
            {label}
            {required && (
              <span className="ml-0.5 text-danger-500">*</span>
            )}
          </label>
        )}

        <div className="relative">
          {leftElement && (
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-neutral-400">
              {leftElement}
            </div>
          )}

          <input
            ref={ref}
            id={inputId}
            required={required}
            className={cn(
              'block w-full rounded-lg border bg-white text-neutral-900',
              'placeholder:text-neutral-400 text-sm',
              'transition-colors duration-150',
              'focus:outline-none focus:ring-2 focus:ring-offset-0',
              'disabled:cursor-not-allowed disabled:bg-neutral-50 disabled:text-neutral-500',
              error
                ? 'border-danger-500 focus:border-danger-500 focus:ring-danger-300'
                : 'border-neutral-300 focus:border-primary-500 focus:ring-primary-200',
              leftElement  ? 'pl-10' : 'pl-3.5',
              rightElement ? 'pr-10' : 'pr-3.5',
              'py-2.5',
              className,
            )}
            {...props}
          />

          {rightElement && (
            <div className="absolute inset-y-0 right-0 flex items-center pr-3 text-neutral-400">
              {rightElement}
            </div>
          )}
        </div>

        {error && (
          <p className="text-xs text-danger-600 flex items-center gap-1">
            <span>{error}</span>
          </p>
        )}

        {!error && helperText && (
          <p className="text-xs text-neutral-500">{helperText}</p>
        )}
      </div>
    );
  },
);

Input.displayName = 'Input';

// ─── Select ───────────────────────────────────────────────────────────────────

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?:      string;
  error?:      string;
  helperText?: string;
  containerClassName?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, helperText, containerClassName, className, id, required, children, ...props }, ref) => {
    const selectId = id ?? label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className={cn('flex flex-col gap-1.5', containerClassName)}>
        {label && (
          <label htmlFor={selectId} className="text-sm font-medium text-neutral-700">
            {label}
            {required && <span className="ml-0.5 text-danger-500">*</span>}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          required={required}
          className={cn(
            'block w-full rounded-lg border bg-white text-neutral-900 text-sm',
            'px-3.5 py-2.5 transition-colors duration-150',
            'focus:outline-none focus:ring-2 focus:ring-offset-0',
            'disabled:cursor-not-allowed disabled:bg-neutral-50',
            error
              ? 'border-danger-500 focus:border-danger-500 focus:ring-danger-300'
              : 'border-neutral-300 focus:border-primary-500 focus:ring-primary-200',
            className,
          )}
          {...props}
        >
          {children}
        </select>
        {error     && <p className="text-xs text-danger-600">{error}</p>}
        {!error && helperText && <p className="text-xs text-neutral-500">{helperText}</p>}
      </div>
    );
  },
);

Select.displayName = 'Select';

// ─── Textarea ─────────────────────────────────────────────────────────────────

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?:      string;
  error?:      string;
  helperText?: string;
  containerClassName?: string;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, helperText, containerClassName, className, id, required, ...props }, ref) => {
    const taId = id ?? label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className={cn('flex flex-col gap-1.5', containerClassName)}>
        {label && (
          <label htmlFor={taId} className="text-sm font-medium text-neutral-700">
            {label}
            {required && <span className="ml-0.5 text-danger-500">*</span>}
          </label>
        )}
        <textarea
          ref={ref}
          id={taId}
          required={required}
          className={cn(
            'block w-full rounded-lg border bg-white text-neutral-900 text-sm',
            'px-3.5 py-2.5 transition-colors duration-150 resize-none',
            'focus:outline-none focus:ring-2 focus:ring-offset-0',
            'disabled:cursor-not-allowed disabled:bg-neutral-50',
            error
              ? 'border-danger-500 focus:border-danger-500 focus:ring-danger-300'
              : 'border-neutral-300 focus:border-primary-500 focus:ring-primary-200',
            className,
          )}
          {...props}
        />
        {error     && <p className="text-xs text-danger-600">{error}</p>}
        {!error && helperText && <p className="text-xs text-neutral-500">{helperText}</p>}
      </div>
    );
  },
);

Textarea.displayName = 'Textarea';
