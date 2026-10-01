/**
 * useCorScreening — signed-in student's COR screening state.
 *
 * load():   GET /cor-screenings/me (the student's latest screening, or none)
 *           plus the campus/program reference lists used by the confirm form.
 * confirm(fields): POST /cor-screenings/confirm — activates the account.
 * resubmit(file):  POST /cor-screenings/resubmit — replaces a failed screening.
 *
 * Session auth (ADR-019) via the API client; the backend authorizes every call.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { request, ApiError } from "../../services/apiClient";
import { FAILURE_REASON_MESSAGES } from "./useRegistration";

/** Friendly text for the documented screening action error codes. */
const ERROR_MESSAGES = {
  EMAIL_ALREADY_REGISTERED: "That email is already registered. Try signing in instead.",
  STUDENT_NUMBER_ALREADY_REGISTERED: "That student number is already registered.",
  COR_MUST_BE_PDF: "Please upload a valid PDF file for your registration form (COR).",
  COR_INVALID_PDF: "That file is not a readable PDF. Please upload your COR again.",
  COR_TOO_LARGE: "The PDF is too large (max 10 MB).",
  SCREENING_UNAVAILABLE:
    "We could not screen your registration form right now. Please try again in a moment.",
  INVALID_STUDENT_NUMBER: "Use your university-issued student number (e.g. 20231234-A).",
  STUDENT_NUMBER_MISMATCH:
    "The student number must match the one on your COR. Reload the page and try again.",
  FIELD_MISMATCH:
    "Some details do not match your COR. Reload the page and try again, or reject and re-upload.",
  SCREENING_EXPIRED: "Your registration form expired. Please upload a new COR.",
  CAMPUS_NOT_FOUND: "Please choose an active campus from the list.",
  PROGRAM_NOT_FOUND: "Please choose an active program from the list.",
  SCREENING_NOT_CONFIRMABLE:
    "These details can no longer be confirmed. Re-upload your COR to continue.",
  SCREENING_NOT_FOUND: "We could not find your registration form. Please upload it again.",
  REGISTRATION_DISABLED: "Registration is temporarily unavailable. Please try again later.",
  FORBIDDEN_ROLE: "This page is for students only.",
  SCREENING_FAILED: "We could not process your registration form. Please try again.",
  ACCOUNT_NOT_REJECTABLE: "Only a registration that is not yet active can be cancelled.",
  FIELD_NOT_EDITABLE: "The student number, academic year, campus, and program cannot be changed here.",
  PROFILE_EDIT_NOT_ALLOWED: "Profile edits can only be requested during registration verification.",
  INVALID_PROFILE_EDIT: "Enter a valid name, year level, and section.",
  CHANGE_REQUEST_PENDING: "You already have an edit request awaiting review.",
  CHANGE_REQUEST_NOT_PENDING: "That edit request has already been decided.",
  CHANGE_REQUEST_REASON_REQUIRED: "Enter a reason for rejecting this request.",
  CHANGE_REQUEST_NOT_FOUND: "That edit request could not be found.",
};

export function failureReasonText(code) {
  if (!code) return "";
  return FAILURE_REASON_MESSAGES[code] ?? code.replaceAll("_", " ").toLowerCase();
}

export const EMPTY_CONFIRM = {
  student_number: "",
  first_name: "",
  middle_name: "",
  last_name: "",
  campus_id: "",
  program_id: "",
  year_level: "",
  section: "",
  academic_period: "",
};

/** Seed the confirm form from a screening's extracted (OCR) fields. */
export function confirmedFieldsFrom(screening) {
  if (!screening) return { ...EMPTY_CONFIRM };
  const value = (raw) => (raw === null || raw === undefined ? "" : String(raw));
  return {
    student_number: value(screening.extracted_student_number),
    first_name: value(screening.extracted_first_name),
    middle_name: value(screening.extracted_middle_name),
    last_name: value(screening.extracted_last_name),
    campus_id: value(screening.extracted_campus_id),
    program_id: value(screening.extracted_program_id),
    year_level: value(screening.extracted_year_level),
    section: value(screening.extracted_section),
    academic_period: value(screening.extracted_academic_period),
  };
}

function toError(err, fallback) {
  if (err instanceof ApiError) return ERROR_MESSAGES[err.code] ?? err.message;
  return fallback;
}

export function useCorScreening() {
  const [screening, setScreening] = useState(null);
  const [campuses, setCampuses] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [referenceError, setReferenceError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const sequence = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      sequence.current++;
    };
  }, []);

  const load = useCallback(async () => {
    const current = ++sequence.current;
    setLoading(true);
    setError("");
    setReferenceError("");
    const [screeningResult, campusResult, programResult] = await Promise.allSettled([
      request("/cor-screenings/me"),
      request("/accounts/campuses"),
      request("/accounts/programs"),
    ]);
    if (current !== sequence.current || !mounted.current) return;
    if (screeningResult.status === "fulfilled") {
      setScreening(screeningResult.value ?? null);
    } else {
      setError(toError(screeningResult.reason, "Could not load your registration status."));
    }
    const missing = [];
    if (campusResult.status === "fulfilled") setCampuses(campusResult.value?.items ?? []);
    else missing.push("campuses");
    if (programResult.status === "fulfilled") setPrograms(programResult.value?.items ?? []);
    else missing.push("programs");
    setReferenceError(missing.length ? `Could not load ${missing.join(" and ")}. Please retry.` : "");
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function confirm(fields) {
    const missing = !fields.student_number || !fields.first_name || !fields.last_name
      || fields.campus_id === "" || fields.program_id === "" || fields.year_level === ""
      || !fields.section;
    if (missing) {
      const text = "Please complete every required field before confirming.";
      setError(text);
      return { success: false, message: text };
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await request("/cor-screenings/confirm", {
        method: "POST",
        body: JSON.stringify({
          student_number: (fields.student_number ?? "").trim(),
          first_name: (fields.first_name ?? "").trim(),
          middle_name: (fields.middle_name ?? "").trim() || null,
          last_name: (fields.last_name ?? "").trim(),
          campus_id: fields.campus_id === "" ? null : Number(fields.campus_id),
          program_id: fields.program_id === "" ? null : Number(fields.program_id),
          year_level: fields.year_level === "" ? null : Number(fields.year_level),
          section: (fields.section ?? "").trim() || null,
          academic_period: (fields.academic_period ?? "").trim() || null,
        }),
      });
      if (mounted.current) {
        setScreening(result?.screening ?? null);
        setMessage("Your enrollment details were confirmed. Your account is now active.");
      }
      return { success: true, data: result };
    } catch (err) {
      const text = toError(err, "Could not confirm your details. Please try again.");
      if (mounted.current) setError(text);
      return { success: false, message: text };
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function requestEdit(fields) {
    const missing = !fields.student_number || !fields.first_name || !fields.last_name
      || fields.campus_id === "" || fields.program_id === "" || fields.year_level === ""
      || !fields.section;
    if (missing) {
      const text = "Please complete every required field before submitting.";
      setError(text);
      return { success: false, message: text };
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await request("/cor-screenings/request-edit", {
        method: "POST",
        body: JSON.stringify({
          student_number: (fields.student_number ?? "").trim(),
          first_name: (fields.first_name ?? "").trim(),
          middle_name: (fields.middle_name ?? "").trim() || null,
          last_name: (fields.last_name ?? "").trim(),
          campus_id: fields.campus_id === "" ? null : Number(fields.campus_id),
          program_id: fields.program_id === "" ? null : Number(fields.program_id),
          year_level: fields.year_level === "" ? null : Number(fields.year_level),
          section: (fields.section ?? "").trim() || null,
          academic_period: (fields.academic_period ?? "").trim() || null,
        }),
      });
      if (mounted.current) {
        setScreening(result?.screening ?? null);
        setMessage(
          result?.change_request
            ? "Account activated. Your requested changes are pending Superadmin approval."
            : "Your enrollment details were confirmed. Your account is now active.",
        );
      }
      return { success: true, data: result, changeRequest: result?.change_request ?? null };
    } catch (err) {
      const text = toError(err, "Could not submit your edit request. Please try again.");
      if (mounted.current) setError(text);
      return { success: false, message: text };
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function reject() {    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await request("/cor-screenings/reject", { method: "POST" });
      if (mounted.current) {
        setScreening(result?.screening ?? null);
        setMessage("We discarded those details. Upload a clearer or corrected COR to continue.");
      }
      return { success: true, data: result };
    } catch (err) {
      const text = toError(err, "Could not reject the extracted details. Please try again.");
      if (mounted.current) setError(text);
      return { success: false, message: text };
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function rejectAccount() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await request("/cor-screenings/reject-account", { method: "POST" });
      return { success: true };
    } catch (err) {
      const text = toError(err, "Could not cancel your registration. Please try again.");
      if (mounted.current) setError(text);
      return { success: false, message: text };
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function resubmit(file) {
    if (!file) {
      setError("Please choose your registration form (COR) PDF.");
      return { success: false };
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await request("/cor-screenings/resubmit", { method: "POST", body });
      if (mounted.current) {
        setScreening(result?.screening ?? null);
        setMessage("Your registration form was received. Review the extracted details and confirm them.");
      }
      return { success: true, data: result };
    } catch (err) {
      const text = toError(err, "Could not upload your registration form. Please try again.");
      if (mounted.current) setError(text);
      return { success: false, message: text };
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  return {
    screening,
    campuses,
    programs,
    loading,
    error,
    referenceError,
    message,
    busy,
    load,
    confirm,
    requestEdit,
    reject,
    rejectAccount,
    resubmit,
    retryReferenceData: load,
  };
}
