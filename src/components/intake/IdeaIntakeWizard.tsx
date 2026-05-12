"use client";

import { useState } from "react";
import { BlueprintPreview } from "@/components/intake/BlueprintPreview";
import { IntakeStep } from "@/components/intake/IntakeStep";
import { generateMockBlueprint } from "@/lib/mock-blueprint";
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

function ProgressRail({
  currentStep,
}: {
  currentStep: number;
}) {
  return (
    <div className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_80px_rgba(0,0,0,0.16)] backdrop-blur-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-emerald-400/80">
            Launch Path
          </p>
          <h2 className="mt-2 text-lg font-semibold text-white">
            Founder intake
          </h2>
        </div>
        <div className="rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs font-medium text-neutral-400">
          {currentStep + 1} / {steps.length}
        </div>
      </div>

      <div className="space-y-3">
        {steps.map((step, index) => {
          const state =
            index < currentStep
              ? "done"
              : index === currentStep
                ? "current"
                : "upcoming";

          return (
            <div
              key={step.title}
              className={`rounded-2xl border px-4 py-4 transition-colors ${
                state === "current"
                  ? "border-emerald-500/30 bg-emerald-500/10"
                  : state === "done"
                    ? "border-white/10 bg-white/6"
                    : "border-white/8 bg-black/25"
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
                    state === "current"
                      ? "bg-emerald-500 text-black"
                      : state === "done"
                        ? "bg-white/12 text-white"
                        : "bg-white/5 text-neutral-500"
                  }`}
                >
                  {index + 1}
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{step.title}</p>
                  <p className="mt-1 text-xs leading-5 text-neutral-400">
                    {step.description}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
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

function FieldWrapper({
  label,
  required,
  helper,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  helper?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-sm font-medium text-white">{label}</span>
        {required ? (
          <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
            Required
          </span>
        ) : null}
      </div>
      {children}
      {helper ? (
        <p className="mt-2 text-xs leading-5 text-neutral-500">{helper}</p>
      ) : null}
      {error ? (
        <p className="mt-2 text-xs font-medium text-rose-300">{error}</p>
      ) : null}
    </label>
  );
}

function TextInput(props: BaseFieldProps) {
  return (
    <FieldWrapper
      label={props.label}
      required={props.required}
      helper={props.helper}
      error={props.error}
    >
      <input
        type="text"
        value={props.value}
        onChange={(event) => props.onChange(props.name, event.target.value)}
        placeholder={props.placeholder}
        className={`w-full rounded-2xl border bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors placeholder:text-neutral-500 ${
          props.error
            ? "border-rose-400/50"
            : "border-white/10 focus:border-emerald-500/50"
        }`}
      />
    </FieldWrapper>
  );
}

function TextArea(props: BaseFieldProps) {
  return (
    <FieldWrapper
      label={props.label}
      required={props.required}
      helper={props.helper}
      error={props.error}
    >
      <textarea
        value={props.value}
        onChange={(event) => props.onChange(props.name, event.target.value)}
        placeholder={props.placeholder}
        rows={5}
        className={`w-full rounded-2xl border bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors placeholder:text-neutral-500 ${
          props.error
            ? "border-rose-400/50"
            : "border-white/10 focus:border-emerald-500/50"
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
      label={props.label}
      required={props.required}
      helper={props.helper}
      error={props.error}
    >
      <select
        value={props.value}
        onChange={(event) => props.onChange(props.name, event.target.value)}
        className={`w-full rounded-2xl border bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors ${
          props.error
            ? "border-rose-400/50"
            : "border-white/10 focus:border-emerald-500/50"
        }`}
      >
        {options.map((option) => (
          <option key={option} value={option} className="bg-neutral-950">
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
    } catch {
      setGenerateState({
        status: "error",
        message: "Could not reach the server. Check your connection and try again.",
      });
    }
  }

  function handleUseDemoBlueprint() {
    setGenerateState({ status: "idle" });
    setBlueprint(generateMockBlueprint(idea));
    setIsPreviewVisible(true);
  }

  function handleEditIdea() {
    setIsPreviewVisible(false);
    setGenerateState({ status: "idle" });
    setCurrentStep(0);
  }

  if (isPreviewVisible && blueprint) {
    return (
      <BlueprintPreview
        idea={idea}
        blueprint={blueprint}
        onEditIdea={handleEditIdea}
      />
    );
  }

  const isLoading = generateState.status === "loading";

  return (
    <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
      <div className="xl:sticky xl:top-28 xl:self-start">
        <ProgressRail currentStep={currentStep} />
      </div>

      <div className="space-y-6">
        <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.18),_transparent_35%),linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] p-6 shadow-[0_30px_120px_rgba(0,0,0,0.45)] sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <div className="inline-flex rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.28em] text-emerald-300">
                Bucks.ai intake
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-5xl">
                Turn an idea into a launch blueprint.
              </h1>
              <p className="mt-4 text-sm leading-7 text-neutral-300 sm:text-base">
                Fill in the four steps below and bucks.ai will generate an
                execution-ready launch plan: stack, GTM, analytics, permissions,
                and next autonomous actions.
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
                  className="rounded-2xl border border-white/10 bg-black/30 px-4 py-4 text-sm text-neutral-300"
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>

        {generateState.status === "missing_key" ? (
          <div className="rounded-[2rem] border border-amber-500/25 bg-amber-500/8 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.3)]">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-amber-500/30 bg-amber-500/15 text-amber-300">
                !
              </div>
              <h3 className="text-sm font-semibold text-amber-200">
                OPENAI_API_KEY not configured
              </h3>
            </div>
            <p className="mb-4 text-sm leading-6 text-amber-100/70">
              To enable real AI blueprint generation, add your OpenAI API key to{" "}
              <code className="rounded bg-black/30 px-1.5 py-0.5 text-amber-200">
                .env.local
              </code>
              :
            </p>
            <pre className="mb-4 overflow-x-auto rounded-2xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-emerald-300">
              {`OPENAI_API_KEY=sk-...`}
            </pre>
            <p className="mb-5 text-sm leading-6 text-neutral-400">
              Restart the dev server after adding the key. In the meantime you
              can explore the demo blueprint below.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={handleUseDemoBlueprint}
                className="rounded-full border border-white/15 bg-white/8 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:border-white/30 hover:bg-white/12"
              >
                Use demo blueprint
              </button>
              <button
                type="button"
                onClick={() => setGenerateState({ status: "idle" })}
                className="rounded-full border border-white/10 bg-transparent px-5 py-2.5 text-sm font-medium text-neutral-400 transition-colors hover:text-white"
              >
                Dismiss
              </button>
            </div>
          </div>
        ) : null}

        {generateState.status === "error" ? (
          <div className="rounded-[2rem] border border-rose-500/25 bg-rose-500/8 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.3)]">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-rose-500/30 bg-rose-500/15 text-rose-300">
                ✕
              </div>
              <h3 className="text-sm font-semibold text-rose-200">
                Blueprint generation failed
              </h3>
            </div>
            <p className="mb-5 text-sm leading-6 text-rose-100/70">
              {generateState.message}
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => void handleGenerateBlueprint()}
                className="rounded-full bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-emerald-400"
              >
                Try again
              </button>
              <button
                type="button"
                onClick={handleUseDemoBlueprint}
                className="rounded-full border border-white/15 bg-white/8 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:border-white/30 hover:bg-white/12"
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

          <div className="mt-10 flex flex-col gap-3 border-t border-white/8 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={handleBack}
              disabled={currentStep === 0 || isLoading}
              className="rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-medium text-white transition-colors hover:border-white/20 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Back
            </button>

            {currentStep < steps.length - 1 ? (
              <button
                type="button"
                onClick={handleContinue}
                disabled={isLoading}
                className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-black transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Continue
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleGenerateBlueprint()}
                disabled={isLoading}
                className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-black transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading ? "Building your blueprint…" : "Generate Blueprint"}
              </button>
            )}
          </div>

          {isLoading ? (
            <div className="mt-4 flex items-center gap-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/8 px-4 py-3">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
              <p className="text-sm text-emerald-300">
                bucks.ai is building your launch blueprint…
              </p>
            </div>
          ) : null}
        </IntakeStep>
      </div>
    </div>
  );
}
