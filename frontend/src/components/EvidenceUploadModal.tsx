import React, { useRef, useState } from 'react';
import { apiClient } from '../services/api/client';
import type { EvidenceUploadProgress } from '../types/evidence';

interface EvidenceUploadModalProps {
  caseId: string;
  caseNumber: string;
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: () => void;
}

export const EvidenceUploadModal: React.FC<EvidenceUploadModalProps> = ({
  caseId,
  caseNumber,
  isOpen,
  onClose,
  onUploadSuccess,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<EvidenceUploadProgress | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const validateFile = (file: File): string | null => {
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (ext !== '.ufdr' && ext !== '.zip') {
      return `Unsupported file format '${ext}'. Forensic evidence upload strictly requires .ufdr or .zip archives.`;
    }
    return null;
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMessage(null);
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const validationError = validateFile(file);
      if (validationError) {
        setErrorMessage(validationError);
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    setErrorMessage(null);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      const validationError = validateFile(file);
      if (validationError) {
        setErrorMessage(validationError);
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMessage('Please select a valid forensic evidence archive (.ufdr or .zip).');
      return;
    }

    setIsUploading(true);
    setIsValidating(false);
    setErrorMessage(null);
    setUploadProgress({ loaded: 0, total: selectedFile.size, percentage: 0 });

    try {
      await apiClient.uploadEvidence(caseId, selectedFile, (prog) => {
        setUploadProgress(prog);
        if (prog.percentage >= 100) {
          setIsValidating(true);
        }
      });

      // Upload and server verification succeeded
      setIsUploading(false);
      setIsValidating(false);
      onUploadSuccess();
      onClose();
    } catch (err: any) {
      setIsUploading(false);
      setIsValidating(false);
      setErrorMessage(err.message || 'Evidence upload failed.');
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <div>
            <h3 style={styles.title}>Secure Evidence Ingestion</h3>
            <div style={styles.subtitle}>
              Uploading forensic package to case <span style={styles.caseBadge}>{caseNumber}</span>
            </div>
          </div>
          <button onClick={onClose} disabled={isUploading} style={styles.closeBtn}>
            ✕
          </button>
        </div>

        {errorMessage && (
          <div style={styles.errorBox}>
            <span style={styles.errorIcon}>⚠</span>
            <div style={styles.errorText}>{errorMessage}</div>
          </div>
        )}

        <form onSubmit={handleUpload} style={styles.form}>
          <div
            style={{
              ...styles.dropZone,
              borderColor: isDragOver ? 'var(--accent-cyan)' : 'var(--border-subtle)',
              backgroundColor: isDragOver ? 'rgba(56, 189, 248, 0.05)' : 'var(--bg-card)',
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            onClick={() => !isUploading && fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept=".ufdr,.zip"
              style={{ display: 'none' }}
              disabled={isUploading}
            />

            <div style={styles.dropIcon}>📦</div>
            <div style={styles.dropPrompt}>
              {selectedFile ? (
                <div>
                  <div style={styles.fileName}>{selectedFile.name}</div>
                  <div style={styles.fileSize}>{formatBytes(selectedFile.size)}</div>
                </div>
              ) : (
                <div>
                  <div>Drag & drop UFDR or ZIP forensic archive here</div>
                  <div style={styles.dropSub}>or click to browse local filesystem</div>
                </div>
              )}
            </div>

            <div style={styles.allowedFormats}>
              SUPPORTED: <span style={styles.formatTag}>.UFDR</span> <span style={styles.formatTag}>.ZIP</span>
            </div>
          </div>

          {/* Upload Progress Bar */}
          {isUploading && (
            <div style={styles.progressContainer}>
              <div style={styles.progressHeader}>
                <span style={styles.progressStatus}>
                  {isValidating
                    ? 'VERIFYING ARCHIVE INTEGRITY & SHA-256...'
                    : 'STREAMING EVIDENCE TO SECURE STORAGE...'}
                </span>
                <span style={styles.progressPercent}>
                  {uploadProgress?.percentage || 0}%
                </span>
              </div>
              <div style={styles.progressBarTrack}>
                <div
                  style={{
                    ...styles.progressBarFill,
                    width: `${uploadProgress?.percentage || 0}%`,
                  }}
                />
              </div>
              <div style={styles.progressDetails}>
                {uploadProgress && (
                  <span>
                    {formatBytes(uploadProgress.loaded)} / {formatBytes(uploadProgress.total)}
                  </span>
                )}
                <span>Direct disk stream (Zero RAM buffer)</span>
              </div>
            </div>
          )}

          <div style={styles.noticeBox}>
            <span style={styles.noticeIcon}>🔒</span>
            <div style={styles.noticeText}>
              Uploaded archives are treated as untrusted input. In-flight SHA-256 checksums are calculated
              concurrently, and ZipSlip defensive inspection is enforced prior to ingestion.
            </div>
          </div>

          <div style={styles.actions}>
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              style={styles.cancelBtn}
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={isUploading || !selectedFile}
              style={{
                ...styles.submitBtn,
                opacity: isUploading || !selectedFile ? 0.6 : 1,
                cursor: isUploading || !selectedFile ? 'not-allowed' : 'pointer',
              }}
            >
              {isUploading
                ? isValidating
                  ? 'VERIFYING...'
                  : 'UPLOADING...'
                : 'START INGESTION'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    backdropFilter: 'blur(4px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    backgroundColor: 'var(--bg-secondary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '8px',
    width: '560px',
    maxWidth: '90vw',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  title: {
    fontSize: '16px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    margin: 0,
    letterSpacing: '0.5px',
  },
  subtitle: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    marginTop: '4px',
  },
  caseBadge: {
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: '16px',
    cursor: 'pointer',
    padding: '4px',
  },
  errorBox: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.4)',
    borderRadius: '4px',
    padding: '12px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  errorIcon: {
    color: 'var(--accent-red)',
    fontSize: '16px',
  },
  errorText: {
    color: 'var(--accent-red)',
    fontSize: '12px',
    lineHeight: '1.4',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  dropZone: {
    border: '2px dashed',
    borderRadius: '6px',
    padding: '32px 20px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    textAlign: 'center',
  },
  dropIcon: {
    fontSize: '36px',
  },
  dropPrompt: {
    fontSize: '13px',
    fontWeight: 500,
    color: 'var(--text-primary)',
  },
  dropSub: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    marginTop: '4px',
  },
  fileName: {
    fontSize: '14px',
    fontWeight: 700,
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
  },
  fileSize: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    marginTop: '4px',
    fontFamily: 'var(--font-mono)',
  },
  allowedFormats: {
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    marginTop: '6px',
  },
  formatTag: {
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-subtle)',
    padding: '2px 6px',
    borderRadius: '3px',
    color: 'var(--text-secondary)',
    margin: '0 2px',
  },
  progressContainer: {
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    padding: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  progressHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
  },
  progressStatus: {
    color: 'var(--accent-cyan)',
    fontWeight: 700,
  },
  progressPercent: {
    color: 'var(--text-primary)',
    fontWeight: 700,
  },
  progressBarTrack: {
    height: '6px',
    backgroundColor: 'var(--bg-primary)',
    borderRadius: '3px',
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: 'var(--accent-cyan)',
    transition: 'width 0.2s ease',
  },
  progressDetails: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '10px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
  noticeBox: {
    backgroundColor: 'rgba(56, 189, 248, 0.05)',
    border: '1px solid rgba(56, 189, 248, 0.2)',
    borderRadius: '4px',
    padding: '10px 12px',
    display: 'flex',
    gap: '10px',
    alignItems: 'flex-start',
  },
  noticeIcon: {
    fontSize: '14px',
    color: 'var(--accent-cyan)',
  },
  noticeText: {
    fontSize: '11px',
    color: 'var(--text-secondary)',
    lineHeight: '1.4',
  },
  actions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '10px',
    marginTop: '8px',
  },
  cancelBtn: {
    backgroundColor: 'transparent',
    color: 'var(--text-muted)',
    border: '1px solid var(--border-subtle)',
    padding: '8px 16px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: 'var(--font-mono)',
    cursor: 'pointer',
  },
  submitBtn: {
    backgroundColor: 'var(--accent-cyan)',
    color: '#000000',
    border: 'none',
    padding: '8px 18px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.5px',
  },
};
