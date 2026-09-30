/**
 * useRegistration — student self-registration (automated COR screening).
 *
 * The student submits ONLY email + password + the current registration form
 * (COR) PDF. The backend screens the PDF synchronously and returns the
 * extracted fields; the student then confirms them from the Registration
 * Status screen. There is no reference-data (campus/program) lookup here.
 */
import { useState } from "react";
import { request, ApiError, setCsrfToken } from "../../services/apiClient";

export const EMPTY_FORM = {
  email: "",
  password: "",
  confirm_password: "",
};

/** Friendly text for the documented registration error codes. */
const ERROR_MESSAGES = {
  EMAIL_ALREADY_REGISTERED: "That email is already registered. Try signing in instead.",
  STUDENT_NUMBER_ALREADY_REGISTERED:
    "That student number is already registered. Sign in to confirm your details.",
  COR_MUST_BE_PDF: "Please upload a valid PDF file for your registration form (COR).",
  COR_INVALID_PDF: "That file is not a readable PDF. Please upload your COR again.",
  COR_TOO_LARGE: "The PDF is too large (max 10 MB).",
  SCREENING_UNAVAILABLE:
    "We could not screen your registration form right now. Please try again in a moment.",
  INVALID_STUDENT_NUMBER: "Use your university-issued student number (e.g. 20231234-A).",
  STUDENT_NUMBER_MISMATCH: "The student number must match the one on your COR. Reload the page and try again.",
  FIELD_MISMATCH: "Some details do not match your COR. Reload the page and try again, or reject and re-upload.",
  CAMPUS_NOT_FOUND: "That campus could not be found. Please try again.",
  PROGRAM_NOT_FOUND: "That program could not be found. Please try again.",
  SCREENING_NOT_CONFIRMABLE: "Your registration form still needs to be reviewed. Please try again.",
  SCREENING_EXPIRED: "Your registration form expired. Please upload a new COR.",
  SCREENING_NOT_FOUND: "We could not find your registration form. Please upload it again.",
  REGISTRATION_DISABLED: "Student registration is temporarily unavailable. Please try again later.",
  FORBIDDEN_ROLE: "This registration path is for students only.",
};

/** Human-readable screening failure reasons (mirrors the backend contract). */
export const FAILURE_REASON_MESSAGES = {
  LOW_FORMAT_SCORE: "The document did not match the expected COR format.",
  LOW_EXTRACTION_CONFIDENCE: "Some required details could not be read clearly.",
  MISSING_REQUIRED_FIELDS: "Required details are missing from the document.",
  UNREADABLE_DOCUMENT: "No readable text was found in the document.",
  TECHNICAL_ERROR: "A technical problem occurred while processing the document.",
  BARCODE_NOT_FOUND: "No barcode was found on the document.",
  BARCODE_UNREADABLE: "The barcode on the document could not be read.",
  BARCODE_INVALID_FORMAT: "The barcode payload format is not valid.",
  BARCODE_MISMATCH: "The barcode does not match the extracted student number.",
  REJECTED_BY_STUDENT: "The extracted details were rejected.",
  ADMIN_RECOVERY: "An administrator reset your enrollment. Please upload a new COR.",
  FIELD_MAPPING_FAILED: "The document details could not be matched to school records.",
};

export function failureReasonText(code) {
  if (!code) return "";
  return FAILURE_REASON_MESSAGES[code] ?? code.replaceAll("_", " ").toLowerCase();
}

/** Friendly message for any post-registration action error (confirm/resubmit). */
export function actionErrorMessage(err) {
  if (err instanceof ApiError) return ERROR_MESSAGES[err.code] ?? err.message;
  return "Something went wrong. Please try again.";
}

/** Outcome copy shown on the register page after a successful submission. */
function outcomeMessage(status) {
  switch (status) {
    case "AWAITING_CONFIRMATION":
      return "Your registration form was read successfully. Review and confirm your details to activate your account.";
    case "NEEDS_RESUBMISSION":
      return "We could not read all of your registration form. Re-upload a clearer copy to continue.";
    case "FAILED":
      return "We could not read your registration form. Re-upload your COR to continue.";
    case "PROCESSING":
      return "Your registration form is being processed. Check back shortly to confirm your details.";
    case "PASSED":
      return "Your registration form was verified.";
    default:
      return "Registration submitted. Review your registration status to continue.";
  }
}

export function useRegistration() {
  const [submitting, setSubmitting] = useState(false);

  async function register(form, corFile) {
    if (!corFile) {
      return {
        success: false,
        message: "Please attach your registration form (COR) PDF — it is required.",
      };
    }
    setSubmitting(true);
    try {
      const body = new FormData();
      body.append("email", form.email);
      body.append("password", form.password);
      body.append("file", corFile);

      const result = await request("/accounts/register/student-with-cor", {
        method: "POST",
        body,
      });
      const screening = result?.screening ?? null;
      const status = screening?.status;
      const failureReason = failureReasonText(screening?.failure_reason_code);

      // Prototype-style flow: establish the session immediately after
      // registration so the student can confirm the extracted details inline
      // without a separate sign-in. A pending account has no confirmed student
      // number yet, so it signs in with its registration email.
      let auth = null;
      try {
        auth = await request("/auth/login", {
          method: "POST",
          body: JSON.stringify({ identifier: form.email, password: form.password }),
        });
        setCsrfToken(auth?.csrf_token ?? null);
      } catch {
        auth = null;
      }

      return {
        success: true,
        outcome: status ?? null,
        screening,
        auth,
        canConfirm: Boolean(auth) && status === "AWAITING_CONFIRMATION",
        unmatched_campus_name: result?.unmatched_campus_name ?? null,
        unmatched_program_name: result?.unmatched_program_name ?? null,
        next_step: result?.next_step ?? null,
        failureReason,
        message: failureReason
          ? `${outcomeMessage(status)} (${failureReason})`
          : outcomeMessage(status),
      };
    } catch (err) {
      if (err instanceof ApiError) {
        return { success: false, code: err.code, message: ERROR_MESSAGES[err.code] ?? err.message };
      }
      return { success: false, message: "Registration failed. Please try again." };
    } finally {
      setSubmitting(false);
    }
  }

  return { register, submitting };
}
