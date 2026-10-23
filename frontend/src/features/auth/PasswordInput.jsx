import { useState } from "react";

/**
 * Password field with a show/hide reveal toggle. Keeps all other input props
 * (id, value, onChange, required, disabled, minLength, autoComplete...)
 * on the native input so callers keep their own validation and tests.
 */
export default function PasswordInput({ id, value, onChange, ...rest }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="input-wrapper">
      <input
        id={id}
        type={visible ? "text" : "password"}
        className="form-input"
        value={value}
        onChange={onChange}
        {...rest}
      />
      <button
        type="button"
        className="password-icon"
        onClick={() => setVisible((current) => !current)}
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
      >
        <i className={visible ? "fa-solid fa-eye-slash" : "fa-solid fa-eye"} aria-hidden="true"></i>
      </button>
    </div>
  );
}
