// Server-side GitHub REST API client.
// All functions require GITHUB_PERSONAL_ACCESS_TOKEN in the environment.
// Never import from client components.

import { getGitHubEnv } from "@/lib/github/env";
import type {
  CreateGitHubRepoInput,
  GitHubRepoRecord,
  CreateGitHubRepoResult,
  GitHubFileTemplate,
} from "@/types/github";

const GITHUB_API_BASE = "https://api.github.com";
const GITHUB_API_VERSION = "2022-11-28";

export type GitHubFileWriteAction = "created" | "updated" | "unchanged";

export interface GitHubFileWriteResult {
  path: string;
  action: GitHubFileWriteAction;
}

export class GitHubFileWriteError extends Error {
  readonly filePath: string;
  readonly status: number;
  readonly operation: "read" | "write";
  readonly githubMessage?: string;

  constructor(input: {
    filePath: string;
    status: number;
    operation: "read" | "write";
    githubMessage?: string;
  }) {
    const verb = input.operation === "read" ? "read" : "write";
    const suffix = input.githubMessage ? `: ${input.githubMessage}` : "";
    super(
      `GitHub file ${verb} failed for ${input.filePath} (${input.status})${suffix}`
    );
    this.name = "GitHubFileWriteError";
    this.filePath = input.filePath;
    this.status = input.status;
    this.operation = input.operation;
    this.githubMessage = input.githubMessage;
  }
}

function githubHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": GITHUB_API_VERSION,
    "Content-Type": "application/json",
  };
}

function encodeGitHubContentPath(path: string) {
  return path.split("/").map(encodeURIComponent).join("/");
}

function getGitHubContentsUrl(input: {
  owner: string;
  repo: string;
  path: string;
  branch?: string;
}) {
  const url = new URL(
    `${GITHUB_API_BASE}/repos/${encodeURIComponent(input.owner)}/${encodeURIComponent(
      input.repo
    )}/contents/${encodeGitHubContentPath(input.path)}`
  );

  if (input.branch) {
    url.searchParams.set("ref", input.branch);
  }

  return url.toString();
}

async function readSafeGitHubMessage(res: Response): Promise<string | undefined> {
  const text = await res.text();
  if (!text.trim()) return undefined;

  try {
    const data = JSON.parse(text) as unknown;
    if (
      typeof data === "object" &&
      data !== null &&
      "message" in data &&
      typeof data.message === "string"
    ) {
      return data.message;
    }
  } catch {
    // Fall through to a bounded plain-text message.
  }

  return text.slice(0, 300);
}

function decodeBase64Content(content: string): string {
  return Buffer.from(content.replace(/\s/g, ""), "base64").toString("utf-8");
}

export interface GitHubAuthenticatedUser {
  login: string;
  id: number;
  name: string | null;
  email: string | null;
}

export async function getAuthenticatedGitHubUser(): Promise<GitHubAuthenticatedUser> {
  const { token } = getGitHubEnv();

  const res = await fetch(`${GITHUB_API_BASE}/user`, {
    headers: githubHeaders(token),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`GitHub /user failed (${res.status}): ${body}`);
  }

  const data = (await res.json()) as GitHubAuthenticatedUser;
  return data;
}

export async function createGitHubRepository(
  input: CreateGitHubRepoInput
): Promise<CreateGitHubRepoResult> {
  const { token } = getGitHubEnv();

  const body = {
    name: input.name,
    description: input.description ?? "",
    private: input.visibility === "private",
    auto_init: false,
  };

  const res = await fetch(`${GITHUB_API_BASE}/user/repos`, {
    method: "POST",
    headers: githubHeaders(token),
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`GitHub repo creation failed (${res.status}): ${errBody}`);
  }

  const repo = (await res.json()) as GitHubRepoRecord;

  return {
    repoUrl: repo.html_url,
    fullName: repo.full_name,
    owner: repo.owner.login,
    name: repo.name,
    repoId: repo.id,
    cloneUrl: repo.clone_url,
    sshUrl: repo.ssh_url,
    private: repo.private,
  };
}

export async function createOrUpdateGitHubFile(input: {
  owner: string;
  repo: string;
  file: GitHubFileTemplate;
  branch?: string;
}): Promise<GitHubFileWriteResult> {
  const { token } = getGitHubEnv();
  const { owner, repo, file, branch } = input;

  const encoded = Buffer.from(file.content, "utf-8").toString("base64");
  const contentsUrl = getGitHubContentsUrl({
    owner,
    repo,
    path: file.path,
    branch,
  });

  const getRes = await fetch(contentsUrl, {
    method: "GET",
    headers: githubHeaders(token),
  });

  let existingSha: string | undefined;

  if (getRes.ok) {
    const existing = (await getRes.json()) as {
      sha?: unknown;
      content?: unknown;
      type?: unknown;
    };

    if (typeof existing.sha !== "string" || existing.type === "dir") {
      throw new GitHubFileWriteError({
        filePath: file.path,
        status: getRes.status,
        operation: "read",
        githubMessage: "Existing path is not a file.",
      });
    }

    existingSha = existing.sha;

    if (
      typeof existing.content === "string" &&
      decodeBase64Content(existing.content) === file.content
    ) {
      return { path: file.path, action: "unchanged" };
    }
  } else if (getRes.status !== 404) {
    throw new GitHubFileWriteError({
      filePath: file.path,
      status: getRes.status,
      operation: "read",
      githubMessage: await readSafeGitHubMessage(getRes),
    });
  }

  const body: {
    message: string;
    content: string;
    branch?: string;
    sha?: string;
  } = {
    message: existingSha ? `Update ${file.path}` : `Create ${file.path}`,
    content: encoded,
  };

  if (branch) body.branch = branch;
  if (existingSha) body.sha = existingSha;

  const res = await fetch(
    getGitHubContentsUrl({
      owner,
      repo,
      path: file.path,
    }),
    {
      method: "PUT",
      headers: githubHeaders(token),
      body: JSON.stringify(body),
    }
  );

  if (!res.ok) {
    throw new GitHubFileWriteError({
      filePath: file.path,
      status: res.status,
      operation: "write",
      githubMessage: await readSafeGitHubMessage(res),
    });
  }

  return { path: file.path, action: existingSha ? "updated" : "created" };
}

export async function createStarterRepositoryFiles(input: {
  owner: string;
  repo: string;
  businessName: string;
  oneLineIdea?: string | null;
}): Promise<void> {
  const { owner, repo, businessName, oneLineIdea } = input;

  const safeName = businessName.trim() || repo;
  const ideaLine = oneLineIdea
    ? `\n> ${oneLineIdea.trim()}\n`
    : "";

  const files: GitHubFileTemplate[] = [
    {
      path: "README.md",
      message: "chore: add starter README",
      content: `# ${safeName}
${ideaLine}
_Generated by [bucks.ai](https://bucks.ai)_

> **Initial scaffold only — no production code generated yet.**

This repository was created automatically as part of the bucks.ai startup operator flow.
A founder or agent will fill in real code once execution begins.
`,
    },
    {
      path: ".gitignore",
      message: "chore: add .gitignore",
      content: `# Dependencies
node_modules/
.pnp
.pnp.js

# Build output
.next/
out/
dist/
build/

# Environment
.env
.env.local
.env.*.local

# Logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Editor
.DS_Store
.vscode/
.idea/
`,
    },
    {
      path: "package.json",
      message: "chore: add placeholder package.json",
      content: JSON.stringify(
        {
          name: repo,
          version: "0.1.0",
          private: true,
          scripts: {
            dev: "echo 'Starter repo created by bucks.ai'",
          },
        },
        null,
        2
      ) + "\n",
    },
    {
      path: "src/README.md",
      message: "chore: add src placeholder",
      content: `# Source

Source code will be generated here by the bucks.ai agent once execution begins.

_Initial scaffold only — no production code generated yet._
`,
    },
  ];

  // Write files serially — GitHub's API can reject parallel writes on a brand-new repo
  for (const file of files) {
    await createOrUpdateGitHubFile({ owner, repo, file });
  }
}
