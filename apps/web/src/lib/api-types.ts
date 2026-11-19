// AUTO-GENERATED FROM apps/api/openapi.json BY scripts/gen_openapi.py — DO NOT EDIT MANUALLY

export interface ApiErrorDetail {
  field?: string | null;
  issue?: string;
  min?: number;
  max?: number;
  [key: string]: unknown;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: ApiErrorDetail[] | Record<string, unknown>;
    request_id: string;
  };
}

export interface OpenApiPaths {
  "/api/v1/account": { methods: "DELETE" };
  "/api/v1/account/export": { methods: "GET" };
  "/api/v1/admin/audit": { methods: "GET" };
  "/api/v1/admin/exercises": { methods: "GET" | "POST" };
  "/api/v1/admin/exercises/{exercise_id}": { methods: "PATCH" };
  "/api/v1/admin/foods": { methods: "GET" | "POST" };
  "/api/v1/admin/foods/{food_id}": { methods: "PATCH" };
  "/api/v1/admin/prices": { methods: "POST" };
  "/api/v1/admin/prices/import": { methods: "POST" };
  "/api/v1/ai/chat": { methods: "POST" };
  "/api/v1/ai/history": { methods: "GET" };
  "/api/v1/ai/proposals/{proposal_id}/confirm": { methods: "POST" };
  "/api/v1/ai/proposals/{proposal_id}/reject": { methods: "POST" };
  "/api/v1/ai/status": { methods: "GET" };
  "/api/v1/auth/change-password": { methods: "POST" };
  "/api/v1/auth/login": { methods: "POST" };
  "/api/v1/auth/logout": { methods: "POST" };
  "/api/v1/auth/me": { methods: "GET" };
  "/api/v1/auth/register": { methods: "POST" };
  "/api/v1/consent": { methods: "GET" | "POST" };
  "/api/v1/dashboard": { methods: "GET" };
  "/api/v1/exercises": { methods: "GET" };
  "/api/v1/foods": { methods: "GET" };
  "/api/v1/health": { methods: "GET" };
  "/api/v1/logs/food": { methods: "POST" | "GET" };
  "/api/v1/logs/food/{log_id}": { methods: "PATCH" | "DELETE" };
  "/api/v1/logs/weight": { methods: "POST" | "GET" };
  "/api/v1/logs/workout": { methods: "POST" | "GET" };
  "/api/v1/logs/workout/{log_id}": { methods: "PATCH" | "DELETE" };
  "/api/v1/meal-plans": { methods: "GET" };
  "/api/v1/meal-plans/generate": { methods: "POST" };
  "/api/v1/meal-plans/{plan_id}": { methods: "GET" | "PATCH" };
  "/api/v1/meal-plans/{plan_id}/confirm": { methods: "POST" };
  "/api/v1/meal-plans/{plan_id}/explanation": { methods: "GET" };
  "/api/v1/meal-plans/{plan_id}/shopping-list": { methods: "GET" };
  "/api/v1/nutrition/estimate": { methods: "POST" };
  "/api/v1/nutrition/target": { methods: "GET" };
  "/api/v1/nutrition/target/history": { methods: "GET" };
  "/api/v1/prices": { methods: "GET" };
  "/api/v1/profile": { methods: "GET" | "PUT" | "PATCH" };
  "/api/v1/workout-plans": { methods: "GET" };
  "/api/v1/workout-plans/generate": { methods: "POST" };
  "/api/v1/workout-plans/{plan_id}": { methods: "GET" | "PATCH" };
  "/api/v1/workout-plans/{plan_id}/confirm": { methods: "POST" };
  "/api/v1/workout-sessions/{session_id}": { methods: "PATCH" };
  "/api/v1/workout-sessions/{session_id}/exercises/{item_id}": { methods: "PATCH" };
  "/health": { methods: "GET" };
}
