/**
 * useRegistration — student self-registration (DFD 1.1 + 1.2 combined):
 * account details AND the registration form (COR) PDF in ONE submission.
 */
import { useEffect, useState } from "react";
import { request, ApiError } from "../../services/apiClient";

export const EMPTY_FORM = {
  email: "",
  password: "",
  first_name: "",
  middle_name: "",
  last_name: "",
  student_number: "",
  campus_id: "",
  program_id: "",
  year_level: "1",
  section: "",
};

export function useRegistration() {
  const [campuses, setCampuses] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [referenceLoading, setReferenceLoading] = useState(true);
  const [referenceError, setReferenceError] = useState("");
  const [referenceVersion, setReferenceVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function loadReferenceData() {
      setReferenceLoading(true);
      setReferenceError("");
      const [campusResult, programResult] = await Promise.allSettled([
        request("/accounts/campuses"),
        request("/accounts/programs"),
      ]);
      if (cancelled) return;
      const errors = [];
      if (campusResult.status === "fulfilled") setCampuses(campusResult.value.items);
      else errors.push("campuses");
      if (programResult.status === "fulfilled") setPrograms(programResult.value.items);
      else errors.push("programs");
      if (errors.length) {
        setReferenceError(`Could not load ${errors.join(" and ")}. Please retry.`);
      }
      setReferenceLoading(false);
    }
    void loadReferenceData();
    return () => {
      cancelled = true;
    };
  }, [referenceVersion]);

  async function register(form, corFile) {
    if (corFile === null) {
      return {
        success: false,
        message: "Please attach your registration form (COR) PDF — it is required.",
      };
    }
    setSubmitting(true);
    try {
      const body = new FormData();
      body.append("first_name", form.first_name);
      body.append("middle_name", form.middle_name || "");
      body.append("last_name", form.last_name);
      body.append("email", form.email);
      body.append("password", form.password);
      body.append("student_number", form.student_number);
      body.append("campus_id", form.campus_id);
      body.append("program_id", form.program_id);
      body.append("year_level", form.year_level);
      body.append("section", form.section);
      body.append("file", corFile);

      await request("/accounts/register/student-with-cor", {
        method: "POST",
        body,
      });
      return {
        success: true,
        message:
          "Registration submitted with your registration form (COR). The Guidance Counselor will review it — you will receive an email once approved or rejected.",
      };
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "EMAIL_ALREADY_REGISTERED") {
          return { success: false, message: "That email is already registered." };
        }
        if (err.code === "STUDENT_NUMBER_ALREADY_REGISTERED") {
          return { success: false, message: "That student number is already registered." };
        }
        if (err.code === "COR_MUST_BE_PDF" || err.code === "COR_INVALID_PDF") {
          return { success: false, message: "Please upload a valid PDF file for your registration form." };
        }
        if (err.code === "COR_TOO_LARGE") {
          return { success: false, message: "The PDF is too large (max 10 MB)." };
        }
        return { success: false, message: err.message };
      }
      return { success: false, message: "Registration failed. Please try again." };
    } finally {
      setSubmitting(false);
    }
  }

  return {
    campuses,
    programs,
    register,
    submitting,
    referenceLoading,
    referenceError,
    retryReferenceData: () => setReferenceVersion((version) => version + 1),
  };
}
