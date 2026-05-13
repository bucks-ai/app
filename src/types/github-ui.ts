export type GitHubRepoVisibility = "private" | "public";

export type GitHubRepoResult = {
  repoUrl: string;
  fullName: string;
  owner: string;
  name: string;
  private: boolean;
};

export type GitHubCreateRepoInput = {
  businessId: string;
  repoName: string;
  visibility: GitHubRepoVisibility;
  includeStarterFiles: boolean;
};

export type GitHubCreateRepoState =
  | {
      status: "idle";
      result: null;
      error: null;
      warning: null;
    }
  | {
      status: "loading";
      result: null;
      error: null;
      warning: null;
    }
  | {
      status: "success";
      result: GitHubRepoResult;
      error: null;
      warning: string | null;
    }
  | {
      status: "error";
      result: null;
      error: string;
      warning: null;
      code?: string;
    };

export type GitHubCreateRepoSuccessResponse = {
  ok: true;
  data: GitHubRepoResult;
  warning?: string;
};

export type GitHubCreateRepoErrorResponse = {
  ok: false;
  code: string;
  error: string;
};

export type GitHubCreateRepoResponse =
  | GitHubCreateRepoSuccessResponse
  | GitHubCreateRepoErrorResponse;
