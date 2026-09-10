/**
 * useRegistration — student self-registration (DFD 1.1 + 1.2 combined):
 * account details AND the registration form (COR) PDF in ONE submission.
 */
import { useEffect, useState } from "react";
import { request, ApiError } from "../../services/apiClient";

export interface Campus {
  campus_id: number;
  campus_name: string;
  guidance_office_location: string | null;
}

export interface Program {
  program_id: number;
  department_id: number;
  program_code: string;
  program_name: string;
}

export interface RegistrationForm {
  email: string;
  password: string;
  first_name: string;
  middle_name: string;
  last_name: string;
  student_number: string;
  campus_id: string;
  program_id: string;
  year_level: string;
  section: string;
}

export const EMPTY_FORM: RegistrationForm = {
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

interface ListEnvelope<T> {
  items: T[];
}

export interface RegistrationResult {
  success: boolean;
  message: string;
}

export function useRegistration() {
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      request<ListEnvelope<Campus>>("/accounts/campuses"),
      request<ListEnvelope<Program>>("/accounts/programs"),
    ])
      .then(([c, p]) => {
        if (!cancelled) {
          setCampuses(c.items);
          setPrograms(p.items);
        }
      })
      .catch(() => {
        /* reference data unavailable; the form shows empty selects */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function register(
    form: RegistrationForm,
    corFile: File | null
  ): Promise<RegistrationResult> {
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

  return { campuses, programs, register, submitting };
}
