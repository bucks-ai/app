"use client";

import { useEffect, useRef, useState } from "react";
import { BlueprintPreview } from "@/components/intake/BlueprintPreview";
import { IntakeStep } from "@/components/intake/IntakeStep";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import { captureIntakeStarted, captureIntakeSubmitted } from "@/lib/analytics/intake";
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

function ProgressRail({
  currentStep,
}: {
  currentStep: number;
}) {
  return (
    <OperatorPanel className="p-4 shadow-[0_24px_80px_rgba(0,0,0,0.32)] sm:p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <SectionLabel>Launch Path</SectionLabel>
          <h2 className="mt-2 text-lg font-semibold text-[#F0F0F0]">
            Founder intake
          </h2>
        </div>
        <StatusPill label={`${currentStep + 1} / ${steps.length}`} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
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
              className={`rounded-lg border px-4 py-4 transition-colors ${
                state === "current"
                  ? "border-[#4F46E5]/60 bg-[#4F46E5]/10"
                  : state === "done"
                    ? "border-[#22C55E]/25 bg-[#22C55E]/10"
                    : "border-[#1C1C1C] bg-[#080808]"
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border font-mono text-xs font-semibold ${
                    state === "current"
                      ? "border-[#4F46E5] bg-[#4F46E5] text-[#F0F0F0]"
                      : state === "done"
                        ? "border-[#22C55E]/35 bg-[#22C55E]/10 text-[#86EFAC]"
                        : "border-[#1C1C1C] bg-[#141414] text-[#888888]"
                  }`}
                >
                  {state === "done" ? "OK" : `0${index + 1}`}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[#F0F0F0]">{step.title}</p>
                  <p className="mt-1 text-xs leading-5 text-[#888888]">
                    {step.description}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
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
        <span className="text-sm font-medium text-[#F0F0F0]">{label}</span>
        {required ? (
          <span className="rounded-md border border-[#4F46E5]/35 bg-[#4F46E5]/10 px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-[#A5B4FC]">
            Required
          </span>
        ) : null}
      </div>
      {children}
      {helper ? (
        <p className="mt-2 text-xs leading-5 text-[#666666]">{helper}</p>
      ) : null}
      {error ? (
        <p className="mt-2 text-xs font-medium text-[#FCA5A5]">{error}</p>
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
        name={props.name}
        value={props.value}
        onChange={(event) => props.onChange(props.name, event.target.value)}
        placeholder={props.placeholder}
        className={`w-full rounded-md border bg-[#080808] px-4 py-3 text-sm text-[#F0F0F0] outline-none transition-colors placeholder:text-[#444444] ${
          props.error
            ? "border-[#EF4444]/60"
            : "border-[#1C1C1C] focus:border-[#4F46E5]"
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
        name={props.name}
        value={props.value}
        onChange={(event) => props.onChange(props.name, event.target.value)}
        placeholder={props.placeholder}
        rows={5}
        className={`w-full rounded-md border bg-[#080808] px-4 py-3 text-sm text-[#F0F0F0] outline-none transition-colors placeholder:text-[#444444] ${
          props.error
            ? "border-[#EF4444]/60"
            : "border-[#1C1C1C] focus:border-[#4F46E5]"
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
        name={props.name}
        value={props.value}
        onChange={(event) => props.onChange(props.name, event.target.value)}
        className={`w-full rounded-md border bg-[#080808] px-4 py-3 text-sm text-[#F0F0F0] outline-none transition-colors ${
          props.error
            ? "border-[#EF4444]/60"
            : "border-[#1C1C1C] focus:border-[#4F46E5]"
        }`}
      >
        {options.map((option) => (
          <option key={option} value={option} className="bg-[#080808]">
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
  const hasCapturedStart = useRef(false);

  useEffect(() => {
    if (hasCapturedStart.current) return;

    hasCapturedStart.current = true;
    captureIntakeStarted();
  }, []);

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
      captureIntakeSubmitted();
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
        <OperatorPanel className="overflow-hidden p-6 shadow-[0_30px_120px_rgba(0,0,0,0.45)] sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <SectionLabel>Bucks.ai intake</SectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
                Turn an idea into a launch blueprint.
              </h1>
              <p className="mt-4 text-sm leading-7 text-[#888888] sm:text-base">
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
                  className="rounded-lg border border-[#1C1C1C] bg-[#080808] px-4 py-4 font-mono text-xs uppercase tracking-[0.16em] text-[#888888]"
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        </OperatorPanel>

        {generateState.status === "missing_key" ? (
          <div className="rounded-lg border border-[#F59E0B]/35 bg-[#F59E0B]/10 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.3)]">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[#F59E0B]/35 bg-[#080808] font-mono text-xs text-[#FCD34D]">
                !
              </div>
              <h3 className="text-sm font-semibold text-[#FCD34D]">
                OPENAI_API_KEY not configured
              </h3>
            </div>
            <p className="mb-4 text-sm leading-6 text-[#FDE68A]/80">
              To enable real AI blueprint generation, add your OpenAI API key to{" "}
              <code className="rounded bg-[#080808] px-1.5 py-0.5 font-mono text-[#FCD34D]">
                .env.local
              </code>
              :
            </p>
            <pre className="mb-4 overflow-x-auto rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 font-mono text-sm text-[#A5B4FC]">
              {`OPENAI_API_KEY=sk-...`}
            </pre>
            <p className="mb-5 text-sm leading-6 text-[#888888]">
              Restart the dev server after adding the key. In the meantime you
              can explore the demo blueprint below.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={handleUseDemoBlueprint}
                className="rounded-md border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-5 py-2.5 text-sm font-medium text-[#FCD34D] transition-colors hover:bg-[#F59E0B]/15"
              >
                Use demo blueprint
              </button>
              <button
                type="button"
                onClick={() => setGenerateState({ status: "idle" })}
                className="rounded-md border border-[#1C1C1C] bg-[#0F0F0F] px-5 py-2.5 text-sm font-medium text-[#888888] transition-colors hover:text-[#F0F0F0]"
              >
                Dismiss
              </button>
            </div>
          </div>
        ) : null}

        {generateState.status === "error" ? (
          <div className="rounded-lg border border-[#EF4444]/35 bg-[#EF4444]/10 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.3)]">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[#EF4444]/35 bg-[#080808] font-mono text-xs text-[#FCA5A5]">
                X
              </div>
              <h3 className="text-sm font-semibold text-[#FCA5A5]">
                Blueprint generation failed
              </h3>
            </div>
            <p className="mb-5 text-sm leading-6 text-[#FECACA]/80">
              {generateState.message}
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => void handleGenerateBlueprint()}
                className="rounded-md bg-[#4F46E5] px-5 py-2.5 text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1]"
              >
                Try again
              </button>
              <button
                type="button"
                onClick={handleUseDemoBlueprint}
                className="rounded-md border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-5 py-2.5 text-sm font-medium text-[#FCD34D] transition-colors hover:bg-[#F59E0B]/15"
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

          <div className="mt-10 flex flex-col gap-3 border-t border-[#1C1C1C] pt-6 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={handleBack}
              disabled={currentStep === 0 || isLoading}
              className="rounded-md border border-[#1C1C1C] bg-[#141414] px-5 py-3 text-sm font-medium text-[#F0F0F0] transition-colors hover:border-[#2A2A2A] hover:bg-[#191919] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Back
            </button>

            {currentStep < steps.length - 1 ? (
              <button
                type="button"
                onClick={handleContinue}
                disabled={isLoading}
                className="rounded-md bg-[#4F46E5] px-6 py-3 text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1] disabled:cursor-not-allowed disabled:opacity-60"
              >
                Continue
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleGenerateBlueprint()}
                disabled={isLoading}
                className="rounded-md bg-[#4F46E5] px-6 py-3 text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading ? "Building your blueprint…" : "Generate Blueprint"}
              </button>
            )}
          </div>

          {isLoading ? (
            <div className="mt-4 rounded-lg border border-[#4F46E5]/35 bg-[#4F46E5]/10 p-4">
              <div className="flex items-center gap-3">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#A5B4FC] border-t-transparent" />
                <p className="text-sm font-medium text-[#A5B4FC]">
                  bucks.ai is building your launch blueprint...
                </p>
              </div>
              <div className="mt-4 grid gap-2 font-mono text-xs text-[#888888] sm:grid-cols-2">
                {[
                  "Classifying business model",
                  "Selecting startup stack",
                  "Mapping GTM motion",
                  "Defining human-only checkpoints",
                  "Preparing launch plan",
                ].map((item) => (
                  <div
                    key={item}
                    className="rounded-md border border-[#1C1C1C] bg-[#080808] px-3 py-2"
                  >
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
