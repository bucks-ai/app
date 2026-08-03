type AuthFieldProps = {
  id: string;
  label: string;
  name: string;
  type: "email" | "password";
  autoComplete: string;
  placeholder: string;
  required?: boolean;
  error?: string;
};

/**
 * One tokenized auth input. Previously each field on /login and /signup
 * carried its own literal hex values, which is how the two pages fell out of
 * sync with the palette and with each other.
 *
 * The visible label is a real `<label htmlFor>`, not a styled `<p>`. It looked
 * identical either way, but with a `<p>` the field had no programmatic label
 * at all and its accessible name fell through to the placeholder — so a
 * screen reader announced the email input as "founder@company.com", voice
 * control had no visible name to target, and the only label disappeared the
 * moment someone started typing. axe passes that pattern, which is why it
 * has to be caught by hand.
 */
export function AuthField({
  id,
  label,
  name,
  type,
  autoComplete,
  placeholder,
  required,
  error,
}: AuthFieldProps) {
  const errorId = `${id}-error`;

  return (
    <div>
      <label
        htmlFor={id}
        className="block font-mono text-xs font-medium uppercase tracking-[0.24em] text-foreground-secondary"
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        name={name}
        autoComplete={autoComplete}
        required={required}
        placeholder={placeholder}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className="mt-2 min-h-12 w-full rounded-xl border border-[var(--input-border)] bg-muted px-4 py-3 text-sm text-foreground outline-none transition-all duration-200 placeholder:text-muted-foreground focus:border-accent/60 focus:shadow-[0_0_0_4px_var(--accent-soft)]"
      />
      {error ? (
        <p id={errorId} className="mt-2 text-sm text-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
