import { NextRequest } from "next/server";
import OpenAI from "openai";
import type { StartupIdea } from "@/types/startup";
import { buildBlueprintPrompt } from "@/lib/blueprint-prompt";
import { requireUser } from "@/lib/api-auth";
import { apiError, badRequest, zodIssuesToFields } from "@/lib/api-error";
import { generateBlueprintBodySchema } from "@/lib/schemas/generate-blueprint";
import { businessBlueprintOutputSchema } from "@/lib/schemas/blueprint-output";

export async function POST(request: NextRequest) {
  const { user, response } = await requireUser();
  if (!user) return response;

  if (!process.env.OPENAI_API_KEY) {
    return Response.json(
      {
        error: "missing_api_key",
        message:
          "OPENAI_API_KEY is not set. Add it to .env.local to enable real blueprint generation.",
      },
      { status: 503 },
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
    return Response.json(
      { error: "model_error", message: `Blueprint generation failed: ${message}` },
      { status: 500 },
    );
  }

  let rawBlueprint: unknown;
  try {
    rawBlueprint = JSON.parse(rawContent);
  } catch {
    return Response.json(
      {
        error: "parse_error",
        message: "The AI returned a response that could not be parsed as JSON.",
      },
      { status: 500 },
    );
  }

  const parsedBlueprint = businessBlueprintOutputSchema.safeParse(rawBlueprint);
  if (!parsedBlueprint.success) {
    console.error(
      "generate-blueprint: AI output failed schema validation.",
      rawContent,
      parsedBlueprint.error.issues,
    );
    return apiError(
      "The AI returned a blueprint that failed validation.",
      "AI_OUTPUT_INVALID",
      502,
    );
  }

  return Response.json({ blueprint: parsedBlueprint.data }, { status: 200 });
}
