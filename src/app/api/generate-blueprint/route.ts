import { NextRequest } from "next/server";
import OpenAI from "openai";
import type { StartupIdea, BusinessBlueprint } from "@/types/startup";
import { buildBlueprintPrompt } from "@/lib/blueprint-prompt";

const REQUIRED_FIELDS: (keyof StartupIdea)[] = [
  "ideaName",
  "oneLineIdea",
  "primaryGoal",
  "budget",
  "timeline",
];

export async function POST(request: NextRequest) {
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

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { error: "invalid_json", message: "Request body must be valid JSON." },
      { status: 400 },
    );
  }

  if (!body || typeof body !== "object") {
    return Response.json(
      { error: "invalid_payload", message: "Request body must be a JSON object." },
      { status: 400 },
    );
  }

  const idea = body as Partial<StartupIdea>;
  const missing = REQUIRED_FIELDS.filter(
    (field) => !idea[field] || String(idea[field]).trim() === "",
  );

  if (missing.length > 0) {
    return Response.json(
      {
        error: "validation_error",
        message: `Missing required fields: ${missing.join(", ")}.`,
        fields: missing,
      },
      { status: 400 },
    );
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
    return Response.json(
      { error: "model_error", message: `Blueprint generation failed: ${message}` },
      { status: 500 },
    );
  }

  let blueprint: BusinessBlueprint;
  try {
    blueprint = JSON.parse(rawContent) as BusinessBlueprint;
  } catch {
    return Response.json(
      {
        error: "parse_error",
        message: "The AI returned a response that could not be parsed as JSON.",
      },
      { status: 500 },
    );
  }

  return Response.json({ blueprint }, { status: 200 });
}
