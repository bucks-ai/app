// Writes a minimal deployable Next.js starter scaffold to an existing GitHub repo.
// Uses createOrUpdateGitHubFile serially — GitHub's API can reject parallel writes on a new repo.

import { createOrUpdateGitHubFile } from "@/lib/github/client";
import { createAgentActivityLog } from "@/lib/projects";

export interface PrepareScaffoldInput {
  businessId: string;
  userId: string;
  owner: string;
  repo: string;
  businessName: string;
  oneLineIdea?: string | null;
}

export interface PrepareScaffoldResult {
  filesWritten: string[];
  activityLogId?: string;
}

export async function prepareDeployableNextScaffold(
  input: PrepareScaffoldInput
): Promise<PrepareScaffoldResult> {
  const { businessId, userId, owner, repo, businessName, oneLineIdea } = input;

  const displayName = businessName.trim() || repo;
  const ideaText = oneLineIdea?.trim() ?? "";

  const files: { path: string; message: string; content: string }[] = [
    {
      path: "package.json",
      message: "chore: add Next.js starter package.json",
      content:
        JSON.stringify(
          {
            name: repo,
            version: "0.1.0",
            private: true,
            scripts: {
              dev: "next dev",
              build: "next build",
              start: "next start",
            },
            dependencies: {
              next: "^15.0.0",
              react: "^19.0.0",
              "react-dom": "^19.0.0",
            },
            devDependencies: {
              typescript: "^5",
              "@types/node": "^20",
              "@types/react": "^19",
              "@types/react-dom": "^19",
            },
          },
          null,
          2
        ) + "\n",
    },
    {
      path: "next.config.ts",
      message: "chore: add next.config.ts",
      content: `import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

export default nextConfig;
`,
    },
    {
      path: "tsconfig.json",
      message: "chore: add tsconfig.json",
      content:
        JSON.stringify(
          {
            compilerOptions: {
              target: "ES2017",
              lib: ["dom", "dom.iterable", "esnext"],
              allowJs: true,
              skipLibCheck: true,
              strict: true,
              noEmit: true,
              esModuleInterop: true,
              module: "esnext",
              moduleResolution: "bundler",
              resolveJsonModule: true,
              isolatedModules: true,
              jsx: "preserve",
              incremental: true,
              plugins: [{ name: "next" }],
              paths: { "@/*": ["./src/*"] },
            },
            include: ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
            exclude: ["node_modules"],
          },
          null,
          2
        ) + "\n",
    },
    {
      path: "src/app/globals.css",
      message: "chore: add globals.css",
      content: `*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --bg: #080808;
  --fg: #f0f0f0;
  --accent: #4f46e5;
  --muted: #888;
  --border: #1f1f1f;
}

body {
  background: var(--bg);
  color: var(--fg);
  font-family: ui-monospace, "Cascadia Code", "Source Code Pro", Menlo, Consolas, monospace;
  font-size: 15px;
  line-height: 1.6;
  min-height: 100vh;
}
`,
    },
    {
      path: "src/app/layout.tsx",
      message: "chore: add root layout",
      content: `import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "${displayName}",
  description: "${ideaText || `${displayName} — powered by bucks.ai`}",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
`,
    },
    {
      path: "src/app/page.tsx",
      message: "chore: add landing page",
      content: `export default function Home() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        gap: "1.5rem",
      }}
    >
      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: "12px",
          padding: "3rem 2.5rem",
          maxWidth: "520px",
          width: "100%",
          background: "#0f0f0f",
        }}
      >
        <p
          style={{
            fontSize: "11px",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--accent)",
            marginBottom: "1rem",
          }}
        >
          bucks.ai operator
        </p>

        <h1
          style={{
            fontSize: "1.75rem",
            fontWeight: 700,
            letterSpacing: "-0.02em",
            marginBottom: "0.75rem",
            color: "var(--fg)",
          }}
        >
          ${displayName}
        </h1>

        ${
          ideaText
            ? `<p
          style={{
            fontSize: "0.95rem",
            color: "var(--muted)",
            marginBottom: "2rem",
            lineHeight: "1.6",
          }}
        >
          ${ideaText}
        </p>`
            : `<p
          style={{
            fontSize: "0.95rem",
            color: "var(--muted)",
            marginBottom: "2rem",
          }}
        >
          Starter project — execution in progress.
        </p>`
        }

        <div
          style={{
            fontSize: "11px",
            color: "#555",
            borderTop: "1px solid var(--border)",
            paddingTop: "1rem",
          }}
        >
          Generated by{" "}
          <a
            href="https://bucks.ai"
            style={{ color: "var(--accent)", textDecoration: "none" }}
          >
            bucks.ai
          </a>
        </div>
      </div>
    </main>
  );
}
`,
    },
    {
      path: "README.md",
      message: "chore: update README with deployable scaffold",
      content: `# ${displayName}
${ideaText ? `\n> ${ideaText}\n` : ""}
_Generated by [bucks.ai](https://bucks.ai)_

## Stack

- [Next.js](https://nextjs.org/) 15
- TypeScript
- No external integrations — clean slate

## Getting Started

\`\`\`bash
npm install
npm run dev
\`\`\`

Open [http://localhost:3000](http://localhost:3000).

## Deploy

This project is linked to Vercel via bucks.ai. Push to \`main\` to trigger a production deployment.

---

_This is a starter scaffold. A founder or agent will add real functionality once execution begins._
`,
    },
  ];

  const filesWritten: string[] = [];

  for (const file of files) {
    await createOrUpdateGitHubFile({ owner, repo, file });
    filesWritten.push(file.path);
  }

  // Log the scaffold preparation
  const logResult = await createAgentActivityLog({
    business_id: businessId,
    user_id: userId,
    activity_type: "github_next_scaffold_prepared",
    message: "Prepared deployable Next.js starter scaffold.",
    metadata: {
      owner,
      repo,
      filesWritten,
    },
  });

  return {
    filesWritten,
    activityLogId: logResult.data?.id ?? undefined,
  };
}
