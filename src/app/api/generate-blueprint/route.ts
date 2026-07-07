import { NextRequest } from "next/server";
import OpenAI from "openai";
import type { StartupIdea } from "@/types/startup";
import { buildBlueprintPrompt } from "@/lib/blueprint-prompt";
import { requireUser } from "@/lib/api-auth";
import { aiOutputInvalid, apiError, badRequest, zodIssuesToFields } from "@/lib/api-error";
import { generateBlueprintBodySchema } from "@/lib/schemas/generate-blueprint";
import { businessBlueprintOutputSchema } from "@/lib/schemas/blueprint-output";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";
import { buildFakeBlueprint, isFakeAiEnabled } from "@/lib/e2e-fake-ai";

export async function POST(request: NextRequest) {
  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:generate-blueprint`, RATE_LIMITS.blueprintGenerate);
  if (!rateLimitResult.allowed) return tooManyRequests();

  const fakeAi = isFakeAiEnabled();

  if (!fakeAi && !process.env.OPENAI_API_KEY) {
    return apiError(
      "OPENAI_API_KEY is not set. Add it to .env.local to enable real blueprint generation.",
      "missing_api_key",
      503,
    );
  }

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = generateBlueprintBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const idea = parsed.data;

  if (fakeAi) {
    const fixture = buildFakeBlueprint(idea);
    const parsedFixture = businessBlueprintOutputSchema.safeParse(fixture);
    if (!parsedFixture.success) {
      console.error(
        "generate-blueprint: E2E_FAKE_AI fixture failed schema validation.",
        JSON.stringify(fixture),
        parsedFixture.error.issues,
      );
      return aiOutputInvalid("The AI returned a blueprint that failed validation.");
    }
    return Response.json({ blueprint: parsedFixture.data }, { status: 200 });
  }

  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const prompt = buildBlueprintPrompt(idea as StartupIdea);

  let rawContent: string;
  try {
    const completion = await client.chat.completions.create({
      model: "gpt-4o",
      messages: [{ role: "user", content: prompt }],
      temperature: 0.7,
      max_tokens: 4096,
      response_format: { type: "json_object" },
    });

    rawContent = completion.choices[0]?.message?.content ?? "";
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown OpenAI API error.";
    return apiError(`Blueprint generation failed: ${message}`, "model_error", 500);
  }

  let rawBlueprint: unknown;
  try {
    rawBlueprint = JSON.parse(rawContent);
  } catch {
    return apiError(
      "The AI returned a response that could not be parsed as JSON.",
      "parse_error",
      500,
    );
  }

  const parsedBlueprint = businessBlueprintOutputSchema.safeParse(rawBlueprint);
  if (!parsedBlueprint.success) {
    console.error(
      "generate-blueprint: AI output failed schema validation.",
      rawContent,
      parsedBlueprint.error.issues,
    );
    return aiOutputInvalid("The AI returned a blueprint that failed validation.");
  }

  return Response.json({ blueprint: parsedBlueprint.data }, { status: 200 });
}
