import { useRef, useState } from "react";

/**
 * CorUpload — dotted-border dropzone for the COR PDF. Click anywhere to choose
 * a file or drop one in. A real (visually hidden) file input stays in the DOM
 * so native `required`/`accept` validation and form submission still apply;
 * a dropped file is mirrored into it.
 */
const isPdf = (file) =>
  file && (file.type === "application/pdf" || /\.pdf$/i.test(file.name ?? ""));

export default function CorUpload({ inputId, title, description, file, onFile,
  required = false, disabled = false }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  function openPicker() {
    if (!disabled) inputRef.current?.click();
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const dropped = Array.from(event.dataTransfer?.files ?? []).find(isPdf);
    if (!dropped) return;
    try {
      // ponytail: mirror into the native input so `required` still passes; the
      // DataTransfer constructor is missing in the test renderer, hence the guard.
      const transfer = new DataTransfer();
      transfer.items.add(dropped);
      if (inputRef.current) inputRef.current.files = transfer.files;
    } catch {
      /* state alone still drives submission */
    }
    onFile(dropped);
  }

  return (
    <div
      className={`upload-box upload-dropzone${dragging ? " is-dragging" : ""}${disabled ? " is-disabled" : ""}`}
      onClick={openPicker}
      onDragEnter={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false); }}
      onDrop={handleDrop}
    >
      <i className="fa-solid fa-file-arrow-up upload-icon" aria-hidden="true"></i>
      <div className="upload-title">{title}</div>
      <div className="upload-desc">{description}</div>
      <span className="upload-browse">{file ? "Choose a different PDF" : "Click to choose a PDF"}</span>
      <span className="upload-or">or drag &amp; drop it here</span>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept="application/pdf,.pdf"
        required={required}
        disabled={disabled}
        className="upload-input"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
      {file && (
        <div className="upload-file">
          <i className="fa-solid fa-file-pdf" aria-hidden="true"></i>
          {file.name}
          {typeof file.size === "number" ? ` (${(file.size / 1024 / 1024).toFixed(2)} MB)` : ""}
        </div>
      )}
    </div>
  );
}
