# FitBudget AI — OpenAPI Reference (Auto-Generated)

Version: `2.0.0`

| Method | Path | Summary | Tags |
|---|---|---|---|
| `DELETE` | `/api/v1/account` | Delete Account | account |
| `GET` | `/api/v1/account/export` | Export Account | account |
| `GET` | `/api/v1/admin/audit` | Admin List Audit | admin |
| `GET` | `/api/v1/admin/exercises` | Admin List Exercises | admin |
| `POST` | `/api/v1/admin/exercises` | Admin Create Exercise | admin |
| `PATCH` | `/api/v1/admin/exercises/{exercise_id}` | Admin Patch Exercise | admin |
| `GET` | `/api/v1/admin/foods` | Admin List Foods | admin |
| `POST` | `/api/v1/admin/foods` | Admin Create Food | admin |
| `PATCH` | `/api/v1/admin/foods/{food_id}` | Admin Patch Food | admin |
| `POST` | `/api/v1/admin/prices` | Admin Create Price | admin |
| `POST` | `/api/v1/admin/prices/import` | Admin Import Prices | admin |
| `POST` | `/api/v1/ai/chat` | Post Chat | ai |
| `GET` | `/api/v1/ai/history` | Get Chat History | ai |
| `POST` | `/api/v1/ai/proposals/{proposal_id}/confirm` | Confirm Proposal Endpoint | ai |
| `POST` | `/api/v1/ai/proposals/{proposal_id}/reject` | Reject Proposal Endpoint | ai |
| `GET` | `/api/v1/ai/status` | Get Ai Status | ai |
| `POST` | `/api/v1/auth/change-password` | Change Password | auth |
| `POST` | `/api/v1/auth/login` | Login | auth |
| `POST` | `/api/v1/auth/logout` | Logout | auth |
| `GET` | `/api/v1/auth/me` | Me | auth |
| `POST` | `/api/v1/auth/register` | Register | auth |
| `GET` | `/api/v1/consent` | Get Consent | account |
| `POST` | `/api/v1/consent` | Post Consent | account |
| `GET` | `/api/v1/dashboard` | Get Dashboard | logs, dashboard |
| `GET` | `/api/v1/exercises` | List Exercises | catalog |
| `GET` | `/api/v1/foods` | List Foods | catalog |
| `GET` | `/api/v1/health` | Health | system |
| `POST` | `/api/v1/logs/food` | Create Food Log | logs, dashboard |
| `GET` | `/api/v1/logs/food` | List Food Logs | logs, dashboard |
| `PATCH` | `/api/v1/logs/food/{log_id}` | Patch Food Log | logs, dashboard |
| `DELETE` | `/api/v1/logs/food/{log_id}` | Delete Food Log | logs, dashboard |
| `POST` | `/api/v1/logs/weight` | Create Or Update Weight Log | logs, dashboard |
| `GET` | `/api/v1/logs/weight` | List Weight Logs | logs, dashboard |
| `POST` | `/api/v1/logs/workout` | Create Workout Log | logs, dashboard |
| `GET` | `/api/v1/logs/workout` | List Workout Logs | logs, dashboard |
| `PATCH` | `/api/v1/logs/workout/{log_id}` | Patch Workout Log | logs, dashboard |
| `DELETE` | `/api/v1/logs/workout/{log_id}` | Delete Workout Log | logs, dashboard |
| `GET` | `/api/v1/meal-plans` | List Meal Plans | meal_plans |
| `POST` | `/api/v1/meal-plans/generate` | Generate Meal Plan Endpoint | meal_plans |
| `GET` | `/api/v1/meal-plans/{plan_id}` | Get Meal Plan | meal_plans |
| `PATCH` | `/api/v1/meal-plans/{plan_id}` | Patch Meal Plan | meal_plans |
| `POST` | `/api/v1/meal-plans/{plan_id}/confirm` | Confirm Meal Plan Endpoint | meal_plans |
| `GET` | `/api/v1/meal-plans/{plan_id}/explanation` | Get Meal Plan Explanation | meal_plans |
| `GET` | `/api/v1/meal-plans/{plan_id}/shopping-list` | Get Shopping List | meal_plans |
| `POST` | `/api/v1/nutrition/estimate` | Post Nutrition Estimate | profile, nutrition |
| `GET` | `/api/v1/nutrition/target` | Get Nutrition Target | profile, nutrition |
| `GET` | `/api/v1/nutrition/target/history` | Get Nutrition Target History | profile, nutrition |
| `GET` | `/api/v1/prices` | List Prices | catalog |
| `GET` | `/api/v1/profile` | Get Profile | profile, nutrition |
| `PUT` | `/api/v1/profile` | Put Profile | profile, nutrition |
| `PATCH` | `/api/v1/profile` | Patch Profile | profile, nutrition |
| `GET` | `/api/v1/workout-plans` | List Workout Plans | workout_plans |
| `POST` | `/api/v1/workout-plans/generate` | Generate Workout Endpoint | workout_plans |
| `GET` | `/api/v1/workout-plans/{plan_id}` | Get Workout Plan | workout_plans |
| `PATCH` | `/api/v1/workout-plans/{plan_id}` | Patch Workout Plan | workout_plans |
| `POST` | `/api/v1/workout-plans/{plan_id}/confirm` | Confirm Workout Endpoint | workout_plans |
| `PATCH` | `/api/v1/workout-sessions/{session_id}` | Patch Workout Session | workout_plans |
| `PATCH` | `/api/v1/workout-sessions/{session_id}/exercises/{item_id}` | Patch Session Exercise | workout_plans |
| `GET` | `/health` | Health | system |
