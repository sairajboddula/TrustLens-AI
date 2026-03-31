import { useState, useCallback } from 'react';
import { useDropzone, FileRejection } from 'react-dropzone';
import { Upload, X, FileImage, AlertCircle, CheckCircle2 } from 'lucide-react';
import { cn } from '@/utils/cn';
import { formatFileSize } from '@/utils/format';
import { Spinner } from '@/components/ui/Spinner';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface UploadedFile {
  file:     File;
  preview?: string;
  progress: number;
  error?:   string;
  uploaded: boolean;
}

export interface DocumentUploadProps {
  label?:          string;
  accept?:         Record<string, string[]>;
  maxSize?:        number;
  value?:          File | null;
  onChange:        (file: File | null) => void;
  error?:          string;
  hint?:           string;
  disabled?:       boolean;
  showPreview?:    boolean;
}

const DEFAULT_ACCEPT: Record<string, string[]> = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png':  ['.png'],
  'image/webp': ['.webp'],
  'application/pdf': ['.pdf'],
};

const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

// ─── Component ────────────────────────────────────────────────────────────────

export function DocumentUpload({
  label        = 'Upload Document',
  accept       = DEFAULT_ACCEPT,
  maxSize      = MAX_SIZE,
  value,
  onChange,
  error,
  hint,
  disabled     = false,
  showPreview  = true,
}: DocumentUploadProps) {
  const [preview,   setPreview]   = useState<string | null>(null);
  const [sizeError, setSizeError] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      setSizeError(null);

      if (rejectedFiles.length > 0) {
        const err = rejectedFiles[0].errors[0];
        if (err.code === 'file-too-large') {
          setSizeError(`File is too large. Maximum size is ${formatFileSize(maxSize)}.`);
        } else if (err.code === 'file-invalid-type') {
          setSizeError('Invalid file type. Please upload an image or PDF.');
        } else {
          setSizeError(err.message);
        }
        return;
      }

      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        onChange(file);

        // Generate preview for images
        if (file.type.startsWith('image/')) {
          const reader = new FileReader();
          reader.onloadend = () => setPreview(reader.result as string);
          reader.readAsDataURL(file);
        } else {
          setPreview(null);
        }
      }
    },
    [onChange, maxSize],
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept,
    maxSize,
    multiple:  false,
    disabled,
  });

  const handleRemove = () => {
    onChange(null);
    setPreview(null);
    setSizeError(null);
  };

  const displayError = error ?? sizeError;

  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-sm font-medium text-neutral-700">{label}</label>
      )}

      {/* Drop zone */}
      {!value ? (
        <div
          {...getRootProps()}
          className={cn(
            'relative flex flex-col items-center justify-center gap-3',
            'border-2 border-dashed rounded-xl px-6 py-8 cursor-pointer',
            'transition-colors duration-150',
            isDragActive && !isDragReject && 'border-primary-400 bg-primary-50',
            isDragReject                   && 'border-danger-400  bg-danger-50',
            !isDragActive && !displayError && 'border-neutral-300 hover:border-primary-400 hover:bg-neutral-50',
            displayError                   && 'border-danger-400  bg-danger-50',
            disabled                       && 'opacity-50 cursor-not-allowed',
          )}
        >
          <input {...getInputProps()} />

          <div
            className={cn(
              'h-12 w-12 rounded-full flex items-center justify-center',
              isDragActive && !isDragReject ? 'bg-primary-100' : 'bg-neutral-100',
              isDragReject && 'bg-danger-100',
            )}
          >
            {isDragReject ? (
              <AlertCircle className="h-6 w-6 text-danger-500" />
            ) : (
              <Upload className={cn('h-6 w-6', isDragActive ? 'text-primary-500' : 'text-neutral-400')} />
            )}
          </div>

          <div className="text-center">
            <p className="text-sm font-medium text-neutral-700">
              {isDragActive
                ? isDragReject
                  ? 'Invalid file type'
                  : 'Drop the file here'
                : 'Drag & drop or click to upload'}
            </p>
            <p className="mt-1 text-xs text-neutral-400">
              {hint ?? `PNG, JPG, PDF up to ${formatFileSize(maxSize)}`}
            </p>
          </div>
        </div>
      ) : (
        /* File preview */
        <div className="relative border-2 border-neutral-200 rounded-xl overflow-hidden bg-neutral-50">
          {/* Remove button */}
          <button
            type="button"
            onClick={handleRemove}
            disabled={disabled}
            className="absolute top-2 right-2 z-10 h-7 w-7 flex items-center justify-center rounded-full bg-white shadow-sm border border-neutral-200 text-neutral-500 hover:text-danger-600 hover:border-danger-300 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>

          {showPreview && preview ? (
            <img
              src={preview}
              alt="Document preview"
              className="w-full h-48 object-contain"
            />
          ) : (
            <div className="flex items-center gap-3 p-4">
              <div className="h-10 w-10 rounded-lg bg-primary-100 flex items-center justify-center shrink-0">
                <FileImage className="h-5 w-5 text-primary-600" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-neutral-800 truncate">{value.name}</p>
                <p className="text-xs text-neutral-400">{formatFileSize(value.size)}</p>
              </div>
              <CheckCircle2 className="h-5 w-5 text-success-500 shrink-0 ml-auto" />
            </div>
          )}

          {showPreview && preview && (
            <div className="px-3 py-2 border-t border-neutral-200 flex items-center gap-2">
              <FileImage className="h-3.5 w-3.5 text-neutral-400 shrink-0" />
              <p className="text-xs text-neutral-600 truncate">{value.name}</p>
              <span className="ml-auto text-xs text-neutral-400">{formatFileSize(value.size)}</span>
            </div>
          )}
        </div>
      )}

      {/* Error message */}
      {displayError && (
        <p className="flex items-center gap-1.5 text-xs text-danger-600">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          {displayError}
        </p>
      )}
    </div>
  );
}

// ─── Multi-document upload (side-by-side) ────────────────────────────────────

export interface DocumentSidesUploadProps {
  label?:       string;
  frontFile:    File | null;
  backFile:     File | null;
  onFrontChange: (f: File | null) => void;
  onBackChange:  (f: File | null) => void;
  frontError?:  string;
  backError?:   string;
  disabled?:    boolean;
}

export function DocumentSidesUpload({
  label        = 'Identity Document',
  frontFile,
  backFile,
  onFrontChange,
  onBackChange,
  frontError,
  backError,
  disabled,
}: DocumentSidesUploadProps) {
  return (
    <div className="space-y-3">
      {label && (
        <p className="text-sm font-semibold text-neutral-700">{label}</p>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <DocumentUpload
          label="Front Side"
          value={frontFile}
          onChange={onFrontChange}
          error={frontError}
          hint="Clear photo of document front"
          disabled={disabled}
        />
        <DocumentUpload
          label="Back Side"
          value={backFile}
          onChange={onBackChange}
          error={backError}
          hint="Clear photo of document back"
          disabled={disabled}
        />
      </div>
    </div>
  );
}
