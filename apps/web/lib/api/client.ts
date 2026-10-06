import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "@/types/api";

export type User = components["schemas"]["UserRead"];
export type AuthResponse = components["schemas"]["AuthResponse"];
export type UserSettings = components["schemas"]["SettingsRead"];
export type Resume = components["schemas"]["ResumeRead"];
export type Profile = components["schemas"]["ProfileRead"];
export type ProfileData = components["schemas"]["ProfileData"];
export type Preferences = components["schemas"]["Preferences"];
export type Skill = components["schemas"]["Skill"];
export type Experience = components["schemas"]["Experience"];
export type JobSummary = components["schemas"]["JobSummary"];
export type JobDetail = components["schemas"]["JobDetail"];
export type SearchRun = components["schemas"]["SearchRunRead"];
export type SourceResult = components["schemas"]["SourceResult"];
export type JobSource = components["schemas"]["JobSourceRead"];
export type Connector = components["schemas"]["ConnectorRead"];
export type EligibilityCheck = components["schemas"]["EligibilityCheckRead"];
export type MatchSummary = components["schemas"]["MatchSummary"];
export type MatchDetail = components["schemas"]["MatchDetail"];
export type MatchStatus = components["schemas"]["MatchStatus"];
export type ScoringSettings = components["schemas"]["ScoringSettings"];
export type Application = components["schemas"]["ApplicationSummary"];
export type ApplicationDetail = components["schemas"]["ApplicationDetail"];
export type Stage = Application["stage"];
export type Interview = components["schemas"]["InterviewRead"];
export type UpcomingInterview = components["schemas"]["UpcomingInterview"];
export type AnalyticsData = components["schemas"]["Analytics"];
export type GroupRates = components["schemas"]["GroupRates"];
export type TailoringSummary = components["schemas"]["TailoringSummary"];
export type TailoringDetail = components["schemas"]["TailoringDetail"];
export type Change = components["schemas"]["Change"];
export type ResumeDocument = components["schemas"]["ResumeDocument"];
export type CoverLetterSummary = components["schemas"]["CoverLetterSummary"];
export type CoverLetterDetail = components["schemas"]["CoverLetterDetail"];
export type LetterParagraph = components["schemas"]["Paragraph"];
export type LetterSentence = components["schemas"]["Sentence"];

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function toApiError(status: number, error: unknown): ApiError {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return new ApiError(status, detail);
  // FastAPI validation errors: surface the first message ("Value error, ..." prefix removed).
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") {
    return new ApiError(status, String(detail[0].msg).replace(/^Value error, /, ""));
  }
  if (status === 422) return new ApiError(status, "Some fields are invalid.");
  if (status === 429) return new ApiError(status, "Too many attempts. Try again in a minute.");
  return new ApiError(status, "Something went wrong. Please try again.");
}

export const api = createClient<paths>({ baseUrl: API_URL, credentials: "include" });

// The CSRF token is kept in memory only. The API also holds it in an httpOnly cookie and
// requires the X-CSRF-Token header to match on every mutating request.
let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  const { data, response } = await api.GET("/api/auth/csrf");
  if (!data) throw new ApiError(response.status, "Could not start a secure session.");
  csrfToken = data.csrf_token;
  return csrfToken;
}

const csrfMiddleware: Middleware = {
  async onRequest({ request }) {
    if (!SAFE_METHODS.has(request.method)) {
      request.headers.set("X-CSRF-Token", await ensureCsrfToken());
    }
    return request;
  },
  async onResponse({ response }) {
    // A stale token (e.g. cookie expired) is dropped so the next mutation fetches a fresh one.
    if (response.status === 403) csrfToken = null;
    return response;
  },
};

api.use(csrfMiddleware);
