import api from './api';
import type { Document, OCRResult, KYCDocumentType } from '@/types';

const DOCS = '/documents';

export const documentService = {
  /**
   * Upload a document file for a KYC submission.
   * Backend expects: file, submission_id, doc_type (Form fields)
   */
  async uploadDocument(
    file: File,
    kycSubmissionId: string,
    docType: KYCDocumentType,
    side: 'FRONT' | 'BACK' | 'SELFIE' = 'FRONT',
    onProgress?: (percent: number) => void,
  ): Promise<unknown> {
    // Map to the DocumentType enum values accepted by the backend.
    // PASSPORT and RESIDENCE_PERMIT have no side variants in the backend enum;
    // NATIONAL_ID and DRIVERS_LICENSE do (e.g. national_id_front / _back).
    let backendDocType: string;
    if (docType === 'PASSPORT') {
      backendDocType = 'passport';
    } else if (docType === 'RESIDENCE_PERMIT') {
      backendDocType = 'residence_permit';
    } else {
      backendDocType = `${docType.toLowerCase()}_${side.toLowerCase()}`;
    }

    const formData = new FormData();
    formData.append('file',          file);
    formData.append('submission_id', kycSubmissionId);
    formData.append('doc_type',      backendDocType);

    const { data } = await api.post(
      `${DOCS}/upload`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          if (onProgress && progressEvent.total) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onProgress(percent);
          }
        },
      },
    );
    return data;
  },

  /**
   * Retrieve document metadata by ID.
   */
  async getDocument(id: string): Promise<Document> {
    const { data } = await api.get<Document>(`${DOCS}/${id}`);
    return data;
  },

  /**
   * Get all documents for a given KYC submission.
   */
  async getDocumentsBySubmission(kycSubmissionId: string): Promise<Document[]> {
    const { data } = await api.get<Document[]>(
      `${DOCS}/submission/${kycSubmissionId}`,
    );
    return data;
  },

  /**
   * Retrieve OCR extraction results for a document.
   */
  async getOCRResults(documentId: string): Promise<OCRResult> {
    const { data } = await api.get<OCRResult>(
      `${DOCS}/${documentId}/ocr`,
    );
    return data;
  },

  /**
   * Delete a document by ID (admin / pre-submission only).
   */
  async deleteDocument(id: string): Promise<void> {
    await api.delete(`${DOCS}/${id}`);
  },
};
