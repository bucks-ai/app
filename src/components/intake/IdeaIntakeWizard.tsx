"use client";

import { useEffect, useState } from "react";
import { BlueprintPreview } from "@/components/intake/BlueprintPreview";
import { IntakeStep } from "@/components/intake/IntakeStep";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import { generateMockBlueprint } from "@/lib/mock-blueprint";
import { createBrowserClient } from "@/lib/supabase/client";
import type {
  AutonomyPreference,
  BusinessBlueprint,
  BusinessTypeGuess,
  StartupIdea,
} from "@/types/startup";

type GenerateState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "missing_key" }
  | { status: "error"; message: string };

type SaveState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "saving" }
  | { status: "saved"; businessId: string; detailUrl: string }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

const businessTypeOptions: BusinessTypeGuess[] = [
  "B2B",
  "B2C",
  "Prosumer",
  "Creator Tool",
  "Agency Tool",
  "Unsure",
];

const autonomyOptions: AutonomyPreference[] = [
  "Recommend only",
  "Ask before major actions",
  "Execute within limits",
  "Maximum autonomy",
];

const initialIdea: StartupIdea = {
  ideaName: "",
  oneLineIdea: "",
  ideaDescription: "",
  targetCustomer: "",
  businessTypeGuess: "Unsure",
  primaryGoal: "",
  successMetric: "",
  budget: "",
  timeline: "",
  autonomyPreference: "Ask before major actions",
  spendingLimit: "",
  hardConstraints: "",
  humanOnlyActions: "",
  forbiddenActions: "",
  preferredTools: "",
};

const steps = [
  {
    title: "Idea Basics",
    description:
      "Define the startup at a glance so bucks.ai can frame the opportunity and the founder promise.",
  },
  {
    title: "Business Goal",
    description:
      "Clarify the model, the primary outcome, and the success signal that should drive execution.",
  },
  {
    title: "Execution Limits",
    description:
      "Set the operating envelope so the system knows how aggressively it can move inside budget and time.",
  },
  {
    title: "Boundaries",
    description:
      "Tell bucks.ai where to stop, what needs approval, and which tools or actions should stay off-limits.",
  },
];

type FieldName = keyof StartupIdea;
type FieldErrors = Partial<Record<FieldName, string>>;

function validateStep(stepIndex: number, idea: StartupIdea): FieldErrors {
  const errors: FieldErrors = {};

  if (stepIndex === 0) {
    if (!idea.ideaName.trim()) {
      errors.ideaName = "Idea name is required.";
    }

    if (!idea.oneLineIdea.trim()) {
      errors.oneLineIdea = "A one-line idea is required.";
    }
  }

  if (stepIndex === 1 && !idea.primaryGoal.trim()) {
    errors.primaryGoal = "Primary goal is required.";
  }

  if (stepIndex === 2) {
    if (!idea.budget.trim()) {
      errors.budget = "Budget is required.";
    }

    if (!idea.timeline.trim()) {
      errors.timeline = "Timeline is required.";
    }
  }

  return errors;
}

function StepNode({ state }: { state: "done" | "current" | "upcoming" }) {
  if (state === "done") {
    return (
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-status-done/40 bg-surface">
        <svg
          aria-hidden
          viewBox="0 0 12 12"
          className="h-3 w-3"
          fill="none"
          stroke="var(--status-done)"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M2 6.5 4.8 9 10 3.5" />
        </svg>
      </span>
    );
  }
  if (state === "current") {
    return (
      <span className="pulse-ring flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-accent bg-accent-soft">
        <span className="h-2 w-2 rounded-full bg-accent" />
      </span>
    );
  }
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-surface">
      <span className="h-2 w-2 rounded-full bg-border-strong" />
    </span>
  );
}

function ProgressRail({
  currentStep,
}: {
  currentStep: number;
}) {
  const progress = ((currentStep + 1) / steps.length) * 100;

  return (
    <OperatorPanel className="p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <SectionLabel>Launch Path</SectionLabel>
          {/* Not an h2: this rail renders above the page h1, so a heading
              here made the document open below its own top level. */}
          <p className="mt-2 text-lg font-semibold text-foreground">
            Founder intake
          </p>
        </div>
        <StatusPill label={`${currentStep + 1} / ${steps.length}`} />
      </div>

      {/* progress rail — same motif as the home pipeline */}
      <div
        className="h-1 overflow-hidden rounded-full bg-border-subtle"
        role="progressbar"
        aria-valuenow={currentStep + 1}
        aria-valuemin={1}
        aria-valuemax={steps.length}
        aria-label={`Step ${currentStep + 1} of ${steps.length}`}
      >
        <div
          className="rail-fill h-full rounded-full bg-accent"
          style={{ width: `${progress}%` }}
        />
      </div>

      <ol className="mt-5 grid gap-0 sm:grid-cols-2 xl:grid-cols-1">
        {steps.map((step, index) => {
          const state =
            index < currentStep
              ? ("done" as const)
              : index === currentStep
                ? ("current" as const)
                : ("upcoming" as const);

          return (
            <li
              key={step.title}
              className="flex gap-3.5"
              aria-current={state === "current" ? "step" : undefined}
            >
              <div className="flex flex-col items-center">
                <StepNode state={state} />
                {index < steps.length - 1 ? (
                  <span
                    aria-hidden
                    className={`my-1 hidden w-px flex-1 xl:block ${
                      state === "done"
                        ? "rail-line-done"
                        : state === "current"
                          ? "flow-line-y"
                          : "rail-line-idle"
                    }`}
                  />
                ) : null}
              </div>
              {/* `opacity-55` here multiplied every descendant's contrast —
                  upcoming step descriptions measured 2.64:1. Upcoming steps
                  are de-emphasised by text colour instead, and the state is
                  now announced rather than implied by dimming. */}
              <div className="min-w-0 pb-6">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    0{index + 1}
                  </span>
                  <p
                    className={`text-sm font-medium ${
                      state === "upcoming"
                        ? "text-foreground-secondary"
                        : "text-foreground"
                    }`}
                  >
                    {step.title}
                  </p>
                  <span className="sr-only">
                    {state === "done"
                      ? "Completed"
                      : state === "current"
                        ? "Current step"
                        : "Not started"}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-foreground-secondary">
                  {step.description}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </OperatorPanel>
  );
}

type BaseFieldProps = {
  label: string;
  name: FieldName;
  value: string;
  error?: string;
  required?: boolean;
  placeholder?: string;
  helper?: string;
  onChange: (name: FieldName, value: string) => void;
};

/** Stable per-field ids so the label and descriptions can be wired by id. */
function fieldIds(name: FieldName) {
  return {
    id: `intake-${name}`,
    helperId: `intake-${name}-helper`,
    errorId: `intake-${name}-error`,
  };
}

/** The describedby list for a field, or undefined when it has neither. */
function describedBy(name: FieldName, helper?: string, error?: string) {
  const { helperId, errorId } = fieldIds(name);
  const ids = [helper ? helperId : null, error ? errorId : null].filter(Boolean);
  return ids.length ? ids.join(" ") : undefined;
}

/*
  This wrapped the label text, the Required chip, the control, the helper
  copy, AND the error in one <label>, so every one of those strings became
  part of the field's accessible name — "Idea Name REQUIRED What should this
  startup or product be called?" announced on every focus, with the error
  appended once validation fired, and no description at all.

  The label element now covers only the label text; helper and error are
  linked through aria-describedby instead.
*/
function FieldWrapper({
  name,
  label,
  required,
  helper,
  error,
  children,
}: {
  name: FieldName;
  label: string;
  required?: boolean;
  helper?: string;
  error?: string;
  children: React.ReactNode;
}) {
  const { id, helperId, errorId } = fieldIds(name);

  return (
    <div className="block">
      <div className="mb-2 flex items-center gap-2">
        <label htmlFor={id} className="text-sm font-medium text-foreground">
          {label}
        </label>
        {required ? (
          <span className="rounded-md border border-accent/35 bg-accent/10 px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-accent-bright">
            Required
          </span>
        ) : null}
      </div>
      {children}
      {helper ? (
        <p id={helperId} className="mt-2 text-xs leading-5 text-muted-foreground">
          {helper}
        </p>
      ) : null}
      {error ? (
        <p
          id={errorId}
          role="alert"
          className="mt-2 text-xs font-medium text-error"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}

function TextInput(props: BaseFieldProps) {
  return (
    <FieldWrapper
      name={props.name}
      label={props.label}
      required={props.required}
      helper={props.helper}
      error={props.error}
    >
      <input
        id={fieldIds(props.name).id}
        type="text"
        aria-required={props.required || undefined}
        aria-describedby={describedBy(props.name, props.helper, props.error)}
        value={props.value}
        onChange={(event) => props.onChange(props.name, event.target.value)}
        placeholder={props.placeholder}
        aria-invalid={props.error ? true : undefined}
        className={`w-full rounded-md border bg-background px-4 py-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-200 placeholder:text-muted-foreground ${
          props.error
            ? "border-error/60"
            : "border-[var(--input-border)] hover:border-border-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-soft)]"
        }`}
      />
    </FieldWrapper>
  );
}

function TextArea(props: BaseFieldProps) {
  return (
    <FieldWrapper
      name={props.name}
      label={props.label}
      required={props.required}
      helper={props.helper}
      error={props.error}
    >
      <textarea
        id={fieldIds(props.name).id}
        aria-required={props.required || undefined}
        aria-describedby={describedBy(props.name, props.helper, props.error)}
        value={props.value}
        onChange={(event) => props.onChange(props.name, event.target.value)}
        placeholder={props.placeholder}
        rows={5}
        aria-invalid={props.error ? true : undefined}
        className={`w-full rounded-md border bg-background px-4 py-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-200 placeholder:text-muted-foreground ${
          props.error
            ? "border-error/60"
            : "border-[var(--input-border)] hover:border-border-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-soft)]"
        }`}
      />
    </FieldWrapper>
  );
}

function SelectField({
  options,
  ...props
}: BaseFieldProps & { options: string[] }) {
  return (
    <FieldWrapper
      name={props.name}
      label={props.label}
      required={props.required}
      helper={props.helper}
      error={props.error}
    >
      <select
        id={fieldIds(props.name).id}
        aria-required={props.required || undefined}
        aria-describedby={describedBy(props.name, props.helper, props.error)}
        value={props.value}
        onChange={(event) => props.onChange(props.name, event.target.value)}
        aria-invalid={props.error ? true : undefined}
        className={`w-full cursor-pointer rounded-md border bg-background px-4 py-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-200 ${
          props.error
            ? "border-error/60"
            : "border-[var(--input-border)] hover:border-border-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-soft)]"
        }`}
      >
        {options.map((option) => (
          <option key={option} value={option} className="bg-background">
            {option}
          </option>
        ))}
      </select>
    </FieldWrapper>
  );
}

export function IdeaIntakeWizard() {
  const [idea, setIdea] = useState<StartupIdea>(initialIdea);
  const [currentStep, setCurrentStep] = useState(0);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [blueprint, setBlueprint] = useState<BusinessBlueprint | null>(null);
  const [isPreviewVisible, setIsPreviewVisible] = useState(false);
  const [generateState, setGenerateState] = useState<GenerateState>({ status: "idle" });
  const [saveState, setSaveState] = useState<SaveState>({ status: "idle" });

  useEffect(() => {
    if (isPreviewVisible) {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [isPreviewVisible]);

  function updateField(name: FieldName, value: string) {
    setIdea((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  }

  function handleContinue() {
    const nextErrors = validateStep(currentStep, idea);
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }

    setErrors({});
    setCurrentStep((step) => Math.min(step + 1, steps.length - 1));
  }

  function handleBack() {
    setErrors({});
    setCurrentStep((step) => Math.max(step - 1, 0));
  }

  async function handleGenerateBlueprint() {
    const nextErrors = {
      ...validateStep(0, idea),
      ...validateStep(1, idea),
      ...validateStep(2, idea),
    };

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      if (nextErrors.ideaName || nextErrors.oneLineIdea) {
        setCurrentStep(0);
      } else if (nextErrors.primaryGoal) {
        setCurrentStep(1);
      } else {
        setCurrentStep(2);
      }
      return;
    }

    setErrors({});
    setGenerateState({ status: "loading" });

    try {
      const response = await fetch("/api/generate-blueprint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(idea),
      });

      const data = (await response.json()) as {
        blueprint?: BusinessBlueprint;
        error?: string;
        message?: string;
      };

      if (!response.ok) {
        if (data.error === "missing_api_key") {
          setGenerateState({ status: "missing_key" });
          return;
        }
        setGenerateState({
          status: "error",
          message: data.message ?? "Blueprint generation failed. Please try again.",
        });
        return;
      }

      if (!data.blueprint) {
        setGenerateState({
          status: "error",
          message: "The server returned an empty blueprint.",
        });
        return;
      }

      setGenerateState({ status: "idle" });
      setBlueprint(data.blueprint);
      setIsPreviewVisible(true);
      void saveGeneratedBlueprint(data.blueprint);
    } catch {
      setGenerateState({
        status: "error",
        message: "Could not reach the server. Check your connection and try again.",
      });
    }
  }

  async function saveGeneratedBlueprint(generatedBlueprint: BusinessBlueprint) {
    setSaveState({ status: "checking" });

    try {
      const supabase = createBrowserClient();
      if (!supabase) {
        setSaveState({ status: "unauthenticated" });
        return;
      }

      const { data, error } = await supabase.auth.getUser();
      if (error || !data.user) {
        setSaveState({ status: "unauthenticated" });
        return;
      }

      setSaveState({ status: "saving" });
      const response = await fetch("/api/businesses/save-blueprint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          startupIdea: idea,
          blueprint: generatedBlueprint,
        }),
      });

      const result = (await response.json()) as
        | { ok: true; businessId: string; detailUrl: string }
        | { ok: false; error?: string; code?: string };

      if (!response.ok || !result.ok) {
        if (!response.ok && response.status === 401) {
          setSaveState({ status: "unauthenticated" });
          return;
        }

        setSaveState({
          status: "error",
          message: result.ok
            ? "Blueprint generated, but saving failed."
            : `Blueprint generated, but saving failed.${result.error ? ` ${result.error}` : ""}`,
        });
        return;
      }

      setSaveState({
        status: "saved",
        businessId: result.businessId,
        detailUrl: result.detailUrl,
      });
    } catch {
      setSaveState({
        status: "error",
        message: "Blueprint generated, but saving failed.",
      });
    }
  }

  function handleUseDemoBlueprint() {
    setGenerateState({ status: "idle" });
    setSaveState({ status: "idle" });
    setBlueprint(generateMockBlueprint(idea));
    setIsPreviewVisible(true);
  }

  function handleEditIdea() {
    setIsPreviewVisible(false);
    setGenerateState({ status: "idle" });
    setSaveState({ status: "idle" });
    setCurrentStep(0);
  }

  if (isPreviewVisible && blueprint) {
    return (
      <BlueprintPreview
        idea={idea}
        blueprint={blueprint}
        onEditIdea={handleEditIdea}
        saveStatus={saveState.status}
        savedBusinessId={saveState.status === "saved" ? saveState.businessId : undefined}
        saveError={saveState.status === "error" ? saveState.message : undefined}
      />
    );
  }

  const isLoading = generateState.status === "loading";

  return (
    <div className="grid gap-6 xl:grid-cols-[330px_minmax(0,1fr)]">
      <div className="xl:sticky xl:top-28 xl:self-start">
        <ProgressRail currentStep={currentStep} />
      </div>

      <div className="space-y-6">
        <OperatorPanel className="overflow-hidden p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <SectionLabel>Bucks.ai intake</SectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-foreground sm:text-5xl">
                Turn an idea into a launch blueprint.
              </h1>
              <p className="mt-4 text-sm leading-7 text-foreground-secondary sm:text-base">
                bucks.ai will generate an execution-ready startup plan: stack,
                GTM, analytics, permissions, and next autonomous actions.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[300px]">
              {[
                "Product scope",
                "Go-to-market motion",
                "Human approvals",
              ].map((item) => (
                <div
                  key={item}
                  className="rounded-lg border border-border bg-background px-4 py-4 font-mono text-xs uppercase tracking-[0.16em] text-foreground-secondary"
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        </OperatorPanel>

        {generateState.status === "missing_key" ? (
          <div className="rounded-lg border border-warning/35 bg-warning/10 p-6">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-md border border-warning/35 bg-background font-mono text-xs text-warning">
                !
              </div>
              <h3 className="text-sm font-semibold text-warning">
                OPENAI_API_KEY not configured
              </h3>
            </div>
            <p className="mb-4 text-sm leading-6 text-foreground-secondary">
              To enable real AI blueprint generation, add your OpenAI API key to{" "}
              <code className="rounded bg-background px-1.5 py-0.5 font-mono text-warning">
                .env.local
              </code>
              :
            </p>
            <pre className="mb-4 overflow-x-auto rounded-md border border-border bg-background px-4 py-3 font-mono text-sm text-accent-bright">
              {`OPENAI_API_KEY=sk-...`}
            </pre>
            <p className="mb-5 text-sm leading-6 text-foreground-secondary">
              Restart the dev server after adding the key. In the meantime you
              can explore the demo blueprint below.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={handleUseDemoBlueprint}
                className="cursor-pointer rounded-md border border-warning/35 bg-warning/10 px-5 py-2.5 text-sm font-medium text-warning transition-colors duration-200 hover:bg-warning/15"
              >
                Use demo blueprint
              </button>
              <button
                type="button"
                onClick={() => setGenerateState({ status: "idle" })}
                className="cursor-pointer rounded-md border border-border bg-surface px-5 py-2.5 text-sm font-medium text-foreground-secondary transition-colors duration-200 hover:text-foreground"
              >
                Dismiss
              </button>
            </div>
          </div>
        ) : null}

        {generateState.status === "error" ? (
          <div role="alert" className="rounded-lg border border-error/35 bg-error/10 p-6">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-md border border-error/35 bg-background font-mono text-xs text-error">
                X
              </div>
              <h3 className="text-sm font-semibold text-error">
                Blueprint generation failed
              </h3>
            </div>
            <p className="mb-5 text-sm leading-6 text-foreground-secondary">
              {generateState.message}
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => void handleGenerateBlueprint()}
                className="cursor-pointer rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-accent-contrast transition-colors duration-200 hover:bg-accent-hover"
              >
                Try again
              </button>
              <button
                type="button"
                onClick={handleUseDemoBlueprint}
                className="cursor-pointer rounded-md border border-warning/35 bg-warning/10 px-5 py-2.5 text-sm font-medium text-warning transition-colors duration-200 hover:bg-warning/15"
              >
                Use demo blueprint
              </button>
            </div>
          </div>
        ) : null}

        <IntakeStep
          step={currentStep + 1}
          totalSteps={steps.length}
          title={steps[currentStep].title}
          description={steps[currentStep].description}
        >
          {currentStep === 0 ? (
            <div className="grid gap-5 lg:grid-cols-2">
              <TextInput
                label="Idea Name"
                name="ideaName"
                value={idea.ideaName}
                error={errors.ideaName}
                required
                placeholder="bucks.ai"
                helper="What should this startup or product be called?"
                onChange={updateField}
              />
              <TextInput
                label="Target Customer"
                name="targetCustomer"
                value={idea.targetCustomer}
                error={errors.targetCustomer}
                placeholder="Solo founders running AI products"
                helper="Who is the first wedge customer?"
                onChange={updateField}
              />
              <div className="lg:col-span-2">
                <TextInput
                  label="One-Line Idea"
                  name="oneLineIdea"
                  value={idea.oneLineIdea}
                  error={errors.oneLineIdea}
                  required
                  placeholder="A self-driving operator for AI/software startups."
                  helper="Describe the startup in one sentence."
                  onChange={updateField}
                />
              </div>
              <div className="lg:col-span-2">
                <TextArea
                  label="Idea Description"
                  name="ideaDescription"
                  value={idea.ideaDescription}
                  error={errors.ideaDescription}
                  placeholder="Describe the product, workflow, or outcome in a bit more detail."
                  helper="Optional, but more detail helps the blueprint feel sharper."
                  onChange={updateField}
                />
              </div>
            </div>
          ) : null}

          {currentStep === 1 ? (
            <div className="grid gap-5 lg:grid-cols-2">
              <SelectField
                label="Business Type Guess"
                name="businessTypeGuess"
                value={idea.businessTypeGuess}
                error={errors.businessTypeGuess}
                options={businessTypeOptions}
                helper="Pick the closest fit. Unsure is fine."
                onChange={updateField}
              />
              <TextInput
                label="Success Metric"
                name="successMetric"
                value={idea.successMetric}
                error={errors.successMetric}
                placeholder="10 qualified founder demos per month"
                helper="What metric would tell you this is working?"
                onChange={updateField}
              />
              <div className="lg:col-span-2">
                <TextArea
                  label="Primary Goal"
                  name="primaryGoal"
                  value={idea.primaryGoal}
                  error={errors.primaryGoal}
                  required
                  placeholder="Validate demand with 5 paying design partners in 8 weeks."
                  helper="This should be the main business outcome bucks.ai optimizes for."
                  onChange={updateField}
                />
              </div>
            </div>
          ) : null}

          {currentStep === 2 ? (
            <div className="grid gap-5 lg:grid-cols-2">
              <TextInput
                label="Budget"
                name="budget"
                value={idea.budget}
                error={errors.budget}
                required
                placeholder="$8,000 to first launch"
                helper="Total budget envelope for the first phase."
                onChange={updateField}
              />
              <TextInput
                label="Timeline"
                name="timeline"
                value={idea.timeline}
                error={errors.timeline}
                required
                placeholder="Launch in 6 weeks"
                helper="How quickly should this move?"
                onChange={updateField}
              />
              <SelectField
                label="Autonomy Preference"
                name="autonomyPreference"
                value={idea.autonomyPreference}
                error={errors.autonomyPreference}
                options={autonomyOptions}
                helper="Choose how aggressively the operator should move."
                onChange={updateField}
              />
              <TextInput
                label="Spending Limit"
                name="spendingLimit"
                value={idea.spendingLimit}
                error={errors.spendingLimit}
                placeholder="$500 without approval"
                helper="Optional approval threshold for spend."
                onChange={updateField}
              />
            </div>
          ) : null}

          {currentStep === 3 ? (
            <div className="grid gap-5 lg:grid-cols-2">
              <TextArea
                label="Hard Constraints"
                name="hardConstraints"
                value={idea.hardConstraints}
                error={errors.hardConstraints}
                placeholder="No custom mobile app. No cold calling. Stay under two paid tools."
                helper="Use commas or new lines if you want to list multiple constraints."
                onChange={updateField}
              />
              <TextArea
                label="Human-Only Actions"
                name="humanOnlyActions"
                value={idea.humanOnlyActions}
                error={errors.humanOnlyActions}
                placeholder="Approving contracts, pricing changes, and live outreach."
                helper="These will be treated as explicit escalation points."
                onChange={updateField}
              />
              <TextArea
                label="Forbidden Actions"
                name="forbiddenActions"
                value={idea.forbiddenActions}
                error={errors.forbiddenActions}
                placeholder="Do not contact current clients. Do not create paid ads."
                helper="Actions bucks.ai should never take autonomously."
                onChange={updateField}
              />
              <TextArea
                label="Preferred Tools"
                name="preferredTools"
                value={idea.preferredTools}
                error={errors.preferredTools}
                placeholder="Vercel, PostHog, HubSpot"
                helper="Optional tool preferences to weave into the plan."
                onChange={updateField}
              />
            </div>
          ) : null}

          <div className="mt-10 flex flex-col gap-3 border-t border-border pt-6 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={handleBack}
              disabled={currentStep === 0 || isLoading}
              className="cursor-pointer rounded-md border border-border bg-surface px-5 py-3 text-sm font-medium text-foreground transition-colors duration-200 hover:border-border-strong hover:bg-elevated disabled:cursor-not-allowed disabled:opacity-40"
            >
              Back
            </button>

            {currentStep < steps.length - 1 ? (
              <button
                type="button"
                onClick={handleContinue}
                disabled={isLoading}
                className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-md bg-accent px-6 py-3 text-sm font-semibold text-accent-contrast transition-colors duration-200 hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
              >
                Continue
                <span aria-hidden className="opacity-80">
                  &#8594;
                </span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleGenerateBlueprint()}
                disabled={isLoading}
                className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-md bg-accent px-6 py-3 text-sm font-semibold text-accent-contrast transition-colors duration-200 hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading ? (
                  <>
                    <span
                      aria-hidden
                      className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-accent-contrast/60 border-t-transparent"
                    />
                    Building your blueprint…
                  </>
                ) : (
                  "Generate Blueprint"
                )}
              </button>
            )}
          </div>

          {/* Content swaps in place here with no navigation, so without a live
              region a screen-reader user gets no signal that generation
              started or finished. */}
          {isLoading ? (
            <div
              role="status"
              aria-live="polite"
              className="mt-4 rounded-lg border border-accent/35 bg-accent/10 p-4"
            >
              <div className="flex items-center gap-3">
                <div
                  aria-hidden
                  className="h-4 w-4 animate-spin rounded-full border-2 border-accent-bright border-t-transparent"
                />
                <p className="text-sm font-medium text-accent-bright">
                  bucks.ai is building your launch blueprint...
                </p>
              </div>
              <div className="mt-4 grid gap-2 font-mono text-xs text-foreground-secondary sm:grid-cols-2">
                {[
                  "Classifying business model",
                  "Selecting startup stack",
                  "Mapping GTM motion",
                  "Defining human-only checkpoints",
                  "Preparing launch plan",
                ].map((item) => (
                  <div
                    key={item}
                    className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2"
                  >
                    <span aria-hidden className="pulse-dot h-1 w-1 rounded-full bg-accent" />
                    {item}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </IntakeStep>
      </div>
    </div>
  );
}
