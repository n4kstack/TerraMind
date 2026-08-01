import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, ImageUp, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

const MAX_BYTES = 10 * 1024 * 1024; // 10 MB
const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp'];

/**
 * Leaf photo input.
 *
 * Offers a distinct "Take photo" action alongside file selection: the primary
 * use case is standing in a field photographing a leaf, and `capture=
 * "environment"` opens the rear camera directly instead of a file browser.
 *
 * The object URL is revoked on replace/unmount — without that, every retry
 * leaks a full-resolution image for the lifetime of the page.
 */
export function ImageDropzone({
  file,
  onSelect,
  onClear,
  disabled,
}: {
  file: File | null;
  onSelect: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const accept = useCallback(
    (candidate: File | undefined) => {
      if (!candidate) return;
      if (!ACCEPTED.includes(candidate.type)) {
        setError('Please choose a JPEG, PNG or WebP image.');
        return;
      }
      if (candidate.size > MAX_BYTES) {
        setError(
          `That image is ${(candidate.size / 1024 / 1024).toFixed(1)} MB. Please use one under 10 MB.`,
        );
        return;
      }
      setError(null);
      onSelect(candidate);
    },
    [onSelect],
  );

  if (file && preview) {
    return (
      <div className="space-y-3">
        <div className="relative overflow-hidden rounded-lg border border-border bg-muted">
          <img
            src={preview}
            alt="Selected leaf photograph, ready for diagnosis"
            className="mx-auto max-h-80 w-full object-contain"
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={onClear}
            disabled={disabled}
            aria-label="Remove image and choose another"
            className="absolute right-3 top-3 bg-card/90 backdrop-blur"
          >
            <X aria-hidden="true" />
          </Button>
        </div>
        <p className="truncate text-xs text-muted-foreground">
          {file.name} · {(file.size / 1024).toFixed(0)} KB
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          accept(e.dataTransfer.files[0]);
        }}
        className={cn(
          'rounded-lg border-2 border-dashed p-8 text-center transition-colors duration-200',
          dragging ? 'border-primary bg-primary/[0.06]' : 'border-border-input bg-muted/30',
        )}
      >
        <span className="mx-auto grid size-14 place-items-center rounded-lg bg-primary/10 text-primary">
          <ImageUp className="size-7" aria-hidden="true" />
        </span>
        <p className="mt-4 font-semibold text-foreground">Add a photo of the affected leaf</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Fill the frame with a single leaf, in daylight, against a plain background.
        </p>

        <div className="mt-5 flex flex-col justify-center gap-2 sm:flex-row">
          <Button type="button" onClick={() => cameraInput.current?.click()} disabled={disabled}>
            <Camera aria-hidden="true" />
            Take photo
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => fileInput.current?.click()}
            disabled={disabled}
          >
            Choose file
          </Button>
        </div>

        <p className="mt-3 text-xs text-muted-foreground">JPEG, PNG or WebP · up to 10 MB</p>

        <input
          ref={fileInput}
          type="file"
          accept={ACCEPTED.join(',')}
          className="sr-only"
          aria-label="Choose a leaf image file"
          onChange={(e) => accept(e.target.files?.[0])}
        />
        <input
          ref={cameraInput}
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          aria-label="Take a photo of the leaf"
          onChange={(e) => accept(e.target.files?.[0])}
        />
      </div>

      {error && (
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
