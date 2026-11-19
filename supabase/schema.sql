-- Generated from SQLAlchemy models. Apply only to an empty FitBudget database.

SET search_path TO public;


CREATE TABLE exercises (
	id VARCHAR(36) NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	pattern VARCHAR(20) NOT NULL, 
	muscle_group VARCHAR(40) NOT NULL, 
	equipment VARCHAR(12) NOT NULL, 
	difficulty INTEGER NOT NULL, 
	rank INTEGER NOT NULL, 
	sets INTEGER NOT NULL, 
	reps_min INTEGER NOT NULL, 
	reps_max INTEGER NOT NULL, 
	unit VARCHAR(10) NOT NULL, 
	rest_s INTEGER NOT NULL, 
	instructions TEXT NOT NULL, 
	contraindication_notes TEXT NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_ex_pattern CHECK (pattern IN ('squat','hinge','lunge','horizontal_push','horizontal_pull','vertical_push','vertical_pull','core','carry')), 
	CONSTRAINT ck_ex_equipment CHECK (equipment IN ('bodyweight','dumbbell','gym')), 
	CONSTRAINT ck_ex_difficulty CHECK (difficulty BETWEEN 1 AND 2), 
	CONSTRAINT ck_ex_unit CHECK (unit IN ('reps','seconds')), 
	UNIQUE (code)
)

;

ALTER TABLE public."exercises" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."exercises" FROM anon, authenticated, PUBLIC;


CREATE TABLE foods (
	id VARCHAR(36) NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	food_group VARCHAR(20) NOT NULL, 
	slots VARCHAR(4) NOT NULL, 
	edible_pct INTEGER NOT NULL, 
	kcal_100g NUMERIC(6, 1) NOT NULL, 
	protein_100g NUMERIC(5, 1) NOT NULL, 
	fat_100g NUMERIC(5, 1), 
	carb_100g NUMERIC(5, 1), 
	step_g INTEGER NOT NULL, 
	min_g INTEGER NOT NULL, 
	max_g INTEGER NOT NULL, 
	max_days_wk INTEGER NOT NULL, 
	source_id VARCHAR(80), 
	verified BOOLEAN NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_foods_group CHECK (food_group IN ('carb','protein_animal','protein_plant','vegetable','fruit','dairy','fat')), 
	CONSTRAINT ck_foods_edible CHECK (edible_pct BETWEEN 1 AND 100), 
	UNIQUE (code)
)

;

ALTER TABLE public."foods" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."foods" FROM anon, authenticated, PUBLIC;


CREATE TABLE system_state (
	key VARCHAR(50) NOT NULL, 
	value VARCHAR(200) NOT NULL, 
	PRIMARY KEY (key)
)

;

ALTER TABLE public."system_state" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."system_state" FROM anon, authenticated, PUBLIC;


CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	failed_login_count INTEGER NOT NULL, 
	first_failed_at TIMESTAMP WITH TIME ZONE, 
	locked_until TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_users_role CHECK (role IN ('user','admin')), 
	UNIQUE (email)
)

;

ALTER TABLE public."users" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."users" FROM anon, authenticated, PUBLIC;


CREATE TABLE admin_audit_log (
	id VARCHAR(36) NOT NULL, 
	admin_id VARCHAR(36), 
	action VARCHAR(30) NOT NULL, 
	entity VARCHAR(30) NOT NULL, 
	entity_id VARCHAR(64), 
	before_json JSON, 
	after_json JSON, 
	reason TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admin_id) REFERENCES users (id) ON DELETE SET NULL
)

;

ALTER TABLE public."admin_audit_log" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."admin_audit_log" FROM anon, authenticated, PUBLIC;


CREATE TABLE ai_cache (
	key VARCHAR(64) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	response_json JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

ALTER TABLE public."ai_cache" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."ai_cache" FROM anon, authenticated, PUBLIC;


CREATE TABLE ai_interactions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	provider VARCHAR(20) NOT NULL, 
	model VARCHAR(60) NOT NULL, 
	intent VARCHAR(40), 
	status VARCHAR(20) NOT NULL, 
	latency_ms INTEGER NOT NULL, 
	tokens_in INTEGER, 
	tokens_out INTEGER, 
	request_id VARCHAR(40) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_aii_status CHECK (status IN ('ok','timeout','error','rate_limited','invalid_output','fallback_template','safety','cache')), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_ai_interactions_user_created ON ai_interactions (user_id, created_at);

ALTER TABLE public."ai_interactions" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."ai_interactions" FROM anon, authenticated, PUBLIC;


CREATE TABLE ai_proposals (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	conversation_id VARCHAR(36) NOT NULL, 
	type VARCHAR(30) NOT NULL, 
	params_json JSON NOT NULL, 
	preview_json JSON NOT NULL, 
	base_plan_type VARCHAR(10), 
	base_plan_id VARCHAR(36), 
	base_version INTEGER, 
	status VARCHAR(10) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_prop_type CHECK (type IN ('change_budget','exclude_food','reschedule_workout')), 
	CONSTRAINT ck_prop_status CHECK (status IN ('pending','confirmed','rejected','expired','failed')), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_ai_proposals_user_id ON ai_proposals (user_id);

ALTER TABLE public."ai_proposals" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."ai_proposals" FROM anon, authenticated, PUBLIC;


CREATE TABLE chat_messages (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	conversation_id VARCHAR(36) NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	content TEXT NOT NULL, 
	intent VARCHAR(40), 
	meta_json JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_chat_role CHECK (role IN ('user','assistant')), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_chat_user_conv ON chat_messages (user_id, conversation_id, created_at);

ALTER TABLE public."chat_messages" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."chat_messages" FROM anon, authenticated, PUBLIC;


CREATE TABLE consents (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	consent_version VARCHAR(20) NOT NULL, 
	data_processing BOOLEAN NOT NULL, 
	ai_cloud BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_consents_user_id ON consents (user_id);

ALTER TABLE public."consents" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."consents" FROM anon, authenticated, PUBLIC;


CREATE TABLE food_aliases (
	id VARCHAR(36) NOT NULL, 
	food_id VARCHAR(36) NOT NULL, 
	alias VARCHAR(120) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(food_id) REFERENCES foods (id) ON DELETE CASCADE
)

;

ALTER TABLE public."food_aliases" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."food_aliases" FROM anon, authenticated, PUBLIC;


CREATE TABLE food_prices (
	id VARCHAR(36) NOT NULL, 
	food_id VARCHAR(36) NOT NULL, 
	region VARCHAR(40) NOT NULL, 
	package_g INTEGER NOT NULL, 
	price_idr INTEGER NOT NULL, 
	recorded_at DATE NOT NULL, 
	source VARCHAR(200) NOT NULL, 
	created_by VARCHAR(36), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_prices_package CHECK (package_g > 0), 
	CONSTRAINT ck_prices_price CHECK (price_idr > 0), 
	FOREIGN KEY(food_id) REFERENCES foods (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
)

;

CREATE INDEX ix_food_prices_lookup ON food_prices (food_id, region, recorded_at);

ALTER TABLE public."food_prices" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."food_prices" FROM anon, authenticated, PUBLIC;


CREATE TABLE meal_plans (
	id VARCHAR(36) NOT NULL, 
	group_id VARCHAR(36) NOT NULL, 
	version INTEGER NOT NULL, 
	parent_id VARCHAR(36), 
	user_id VARCHAR(36) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	result_status VARCHAR(12) NOT NULL, 
	start_date DATE NOT NULL, 
	budget_limit_idr INTEGER NOT NULL, 
	target_energy_kcal INTEGER NOT NULL, 
	target_protein_g INTEGER NOT NULL, 
	generation_params_json JSON NOT NULL, 
	unmet_json JSON NOT NULL, 
	warnings_json JSON NOT NULL, 
	day_status_json JSON NOT NULL, 
	engine_version VARCHAR(30) NOT NULL, 
	catalog_version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	confirmed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_meal_plans_group_version UNIQUE (group_id, version), 
	CONSTRAINT ck_mp_status CHECK (status IN ('draft','confirmed','archived')), 
	CONSTRAINT ck_mp_result CHECK (result_status IN ('FEASIBLE','PARTIAL','INFEASIBLE')), 
	FOREIGN KEY(parent_id) REFERENCES meal_plans (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_meal_plans_user_id ON meal_plans (user_id);

ALTER TABLE public."meal_plans" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."meal_plans" FROM anon, authenticated, PUBLIC;


CREATE TABLE nutrition_targets (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	inputs_json JSON NOT NULL, 
	ree_kcal NUMERIC(7, 1) NOT NULL, 
	tdee_kcal NUMERIC(7, 1) NOT NULL, 
	energy_target_kcal INTEGER NOT NULL, 
	protein_target_g INTEGER NOT NULL, 
	warnings_json JSON NOT NULL, 
	result_json JSON NOT NULL, 
	formula_version VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_nutrition_targets_user_id ON nutrition_targets (user_id);

ALTER TABLE public."nutrition_targets" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."nutrition_targets" FROM anon, authenticated, PUBLIC;


CREATE TABLE plan_change_log (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	plan_type VARCHAR(10) NOT NULL, 
	plan_id VARCHAR(36) NOT NULL, 
	from_version INTEGER, 
	to_version INTEGER NOT NULL, 
	source VARCHAR(15) NOT NULL, 
	diff_json JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_pcl_type CHECK (plan_type IN ('meal','workout')), 
	CONSTRAINT ck_pcl_source CHECK (source IN ('user','ai_proposal','system')), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_plan_change_log_user_id ON plan_change_log (user_id);

ALTER TABLE public."plan_change_log" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."plan_change_log" FROM anon, authenticated, PUBLIC;


CREATE TABLE preferences (
	user_id VARCHAR(36) NOT NULL, 
	daily_budget_idr INTEGER NOT NULL, 
	workout_days JSON NOT NULL, 
	session_minutes INTEGER NOT NULL, 
	experience_level VARCHAR(15) NOT NULL, 
	equipment_access VARCHAR(20) NOT NULL, 
	excluded_food_ids JSON NOT NULL, 
	allergies JSON NOT NULL, 
	excluded_exercise_ids JSON NOT NULL, 
	region VARCHAR(40) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

ALTER TABLE public."preferences" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."preferences" FROM anon, authenticated, PUBLIC;


CREATE TABLE profiles (
	user_id VARCHAR(36) NOT NULL, 
	age_years INTEGER NOT NULL, 
	sex VARCHAR(6) NOT NULL, 
	weight_kg NUMERIC(4, 1) NOT NULL, 
	height_cm INTEGER NOT NULL, 
	activity_level VARCHAR(10) NOT NULL, 
	goal VARCHAR(20) NOT NULL, 
	protein_g_per_kg NUMERIC(2, 1) NOT NULL, 
	screening_json JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (user_id), 
	CONSTRAINT ck_profiles_sex CHECK (sex IN ('male','female')), 
	CONSTRAINT ck_profiles_activity CHECK (activity_level IN ('sedentary','light','moderate','active')), 
	CONSTRAINT ck_profiles_goal CHECK (goal IN ('maintain','build_strength','lose_weight')), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

ALTER TABLE public."profiles" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."profiles" FROM anon, authenticated, PUBLIC;


CREATE TABLE weight_logs (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	date DATE NOT NULL, 
	weight_kg NUMERIC(4, 1) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_weight_user_date UNIQUE (user_id, date), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

ALTER TABLE public."weight_logs" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."weight_logs" FROM anon, authenticated, PUBLIC;


CREATE TABLE workout_plans (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	week_start DATE NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	version INTEGER NOT NULL, 
	warnings_json JSON NOT NULL, 
	params_json JSON NOT NULL, 
	engine_version VARCHAR(30) NOT NULL, 
	catalog_version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_wp_status CHECK (status IN ('draft','confirmed','archived')), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_workout_plans_user_id ON workout_plans (user_id);

ALTER TABLE public."workout_plans" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."workout_plans" FROM anon, authenticated, PUBLIC;


CREATE TABLE food_logs (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	date DATE NOT NULL, 
	meal_slot VARCHAR(10) NOT NULL, 
	food_id VARCHAR(36) NOT NULL, 
	grams INTEGER NOT NULL, 
	energy_kcal NUMERIC(7, 1) NOT NULL, 
	protein_g NUMERIC(6, 1) NOT NULL, 
	cost_idr INTEGER NOT NULL, 
	price_id VARCHAR(36), 
	cost_is_actual BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_fl_grams CHECK (grams > 0), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(food_id) REFERENCES foods (id), 
	FOREIGN KEY(price_id) REFERENCES food_prices (id)
)

;

CREATE INDEX ix_food_logs_user_date ON food_logs (user_id, date);

ALTER TABLE public."food_logs" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."food_logs" FROM anon, authenticated, PUBLIC;


CREATE TABLE meal_plan_items (
	id VARCHAR(36) NOT NULL, 
	meal_plan_id VARCHAR(36) NOT NULL, 
	date DATE NOT NULL, 
	meal_slot VARCHAR(10) NOT NULL, 
	food_id VARCHAR(36) NOT NULL, 
	grams INTEGER NOT NULL, 
	price_id VARCHAR(36) NOT NULL, 
	cost_idr INTEGER NOT NULL, 
	energy_kcal NUMERIC(7, 1) NOT NULL, 
	protein_g NUMERIC(6, 1) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_mpi_slot CHECK (meal_slot IN ('breakfast','lunch','dinner','snack')), 
	FOREIGN KEY(meal_plan_id) REFERENCES meal_plans (id) ON DELETE CASCADE, 
	FOREIGN KEY(food_id) REFERENCES foods (id), 
	FOREIGN KEY(price_id) REFERENCES food_prices (id)
)

;

CREATE INDEX ix_meal_plan_items_meal_plan_id ON meal_plan_items (meal_plan_id);

ALTER TABLE public."meal_plan_items" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."meal_plan_items" FROM anon, authenticated, PUBLIC;


CREATE TABLE workout_sessions (
	id VARCHAR(36) NOT NULL, 
	plan_id VARCHAR(36) NOT NULL, 
	date DATE NOT NULL, 
	template_code VARCHAR(10) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	estimated_minutes INTEGER NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_ws_status CHECK (status IN ('planned','completed','skipped')), 
	FOREIGN KEY(plan_id) REFERENCES workout_plans (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_workout_sessions_plan_id ON workout_sessions (plan_id);

ALTER TABLE public."workout_sessions" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."workout_sessions" FROM anon, authenticated, PUBLIC;


CREATE TABLE workout_logs (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	date DATE NOT NULL, 
	session_id VARCHAR(36), 
	exercise_id VARCHAR(36) NOT NULL, 
	sets_json JSON NOT NULL, 
	effort_rating INTEGER, 
	completed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_wl_effort CHECK (effort_rating IS NULL OR effort_rating BETWEEN 1 AND 10), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(session_id) REFERENCES workout_sessions (id) ON DELETE SET NULL, 
	FOREIGN KEY(exercise_id) REFERENCES exercises (id)
)

;

CREATE INDEX ix_workout_logs_user_date ON workout_logs (user_id, date);

ALTER TABLE public."workout_logs" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."workout_logs" FROM anon, authenticated, PUBLIC;


CREATE TABLE workout_session_exercises (
	id VARCHAR(36) NOT NULL, 
	session_id VARCHAR(36) NOT NULL, 
	position INTEGER NOT NULL, 
	exercise_id VARCHAR(36) NOT NULL, 
	sets INTEGER NOT NULL, 
	reps_min INTEGER NOT NULL, 
	reps_max INTEGER NOT NULL, 
	unit VARCHAR(10) NOT NULL, 
	rest_s INTEGER NOT NULL, 
	alternatives_json JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES workout_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(exercise_id) REFERENCES exercises (id)
)

;

CREATE INDEX ix_workout_session_exercises_session_id ON workout_session_exercises (session_id);

ALTER TABLE public."workout_session_exercises" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public."workout_session_exercises" FROM anon, authenticated, PUBLIC;
