/**
 * useCorUpload — submits the registration form (COR) PDF for the signed-in
 * student. multipart/form-data per API_CONTRACT.md; identity comes from the
 * session cookie (ADR-019), not a query parameter.
 */
import { useState } from "react";
import { request, ApiError } from "../../services/apiClient";

export interface CorUploadResult {
  success: boolean;
  message: string;
  status?: string;
}

export function useCorUpload() {
  const [uploading, setUploading] = useState(false);

  async function uploadCor(file: File): Promise<CorUploadResult> {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      return { success: false, message: "The registration form must be a PDF file." };
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const body = await request<{ verification_id: number; status: string }>(
        "/enrollment-verifications/cor",
        { method: "POST", body: form }
      );
      return {
        success: true,
        status: body.status,
        message:
          "Registration form uploaded. The Guidance Counselor will review your application — you will receive an email once decided.",
      };
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "COR_MUST_BE_PDF" || err.code === "COR_INVALID_PDF") {
          return { success: false, message: "Please upload a valid PDF file." };
        }
        if (err.code === "COR_TOO_LARGE") {
          return { success: false, message: "The PDF is too large (max 10 MB)." };
        }
        return { success: false, message: err.message };
      }
      return { success: false, message: "Upload failed. Please try again." };
    } finally {
      setUploading(false);
    }
  }

  return { uploadCor, uploading };
}
