export type ExerciseEquipment = "bodyweight" | "dumbbell" | "gym";
export type ExerciseCategory = "gym" | "workout" | "both";
export type ExerciseModeFilter = "all" | "gym" | "workout";
export type GymSubFilter = "all_gym" | "gym_only" | "dumbbell";
export type WorkoutSubFilter = "bodyweight_only" | "with_dumbbell";

export interface CatalogExercise {
  id: string;
  code: string;
  name: string;
  pattern: string;
  muscle_group: string;
  equipment: ExerciseEquipment;
  category?: ExerciseCategory;
  difficulty: number;
  rank: number;
  sets: number;
  reps_min: number;
  reps_max: number;
  unit: "reps" | "seconds";
  rest_s: number;
  instructions: string;
  contraindication_notes?: string;
  is_active?: boolean;
}

export const MUSCLE_GROUP_LABELS: Record<string, string> = {
  chest: "Dada",
  back: "Punggung",
  shoulders: "Bahu",
  legs: "Kaki & Paha",
  hamstrings: "Hamstring",
  glutes: "Glutes / Bokong",
  calves: "Betis",
  biceps: "Bisep",
  triceps: "Trisep",
  core: "Perut / Core",
  cardio: "Kardio",
  full_body: "Full Body",
};

export const PATTERN_LABELS: Record<string, string> = {
  squat: "Squat",
  hinge: "Hinge",
  lunge: "Lunge",
  horizontal_push: "Dorong Horizontal",
  horizontal_pull: "Tarik Horizontal",
  vertical_push: "Dorong Vertikal",
  vertical_pull: "Tarik Vertikal",
  core: "Core",
  carry: "Carry & Kardio",
};

export const EQUIPMENT_META: Record<
  ExerciseEquipment,
  { badge: string; shortLabel: string; description: string; badgeClass: string }
> = {
  gym: {
    badge: "Gym",
    shortLabel: "Alat Gym",
    description: "Barbell, Mesin, Cable, Bench / Rack",
    badgeClass: "border-accent-line bg-accent-soft text-accent-ink",
  },
  bodyweight: {
    badge: "Workout",
    shortLabel: "Tanpa Alat",
    description: "Home Workout / Calisthenics (Bodyweight)",
    badgeClass: "border-positive-line bg-positive-soft text-positive",
  },
  dumbbell: {
    badge: "Dumbbell",
    shortLabel: "Dumbbell",
    description: "Bisa di Gym maupun Workout Rumahan",
    badgeClass: "border-info-line bg-info-soft text-info",
  },
};

export function formatMuscleLabel(muscle: string): string {
  return MUSCLE_GROUP_LABELS[muscle] || muscle;
}

export function formatPatternLabel(pattern: string): string {
  return PATTERN_LABELS[pattern] || pattern;
}

export function formatRepRange(ex: Pick<CatalogExercise, "reps_min" | "reps_max" | "unit">): string {
  const unitLabel = ex.unit === "seconds" ? "dtk" : "rep";
  return `${ex.reps_min}–${ex.reps_max} ${unitLabel}`;
}

export function filterExercises(
  items: CatalogExercise[],
  opts: {
    mode: ExerciseModeFilter;
    gymSub?: GymSubFilter;
    workoutSub?: WorkoutSubFilter;
    muscleGroup?: string;
    difficulty?: "all" | "1" | "2";
    search?: string;
  },
): CatalogExercise[] {
  const { mode, gymSub = "all_gym", workoutSub = "bodyweight_only", muscleGroup = "", difficulty = "all", search = "" } =
    opts;
  const q = search.trim().toLowerCase();

  return items.filter((ex) => {
    if (mode === "gym") {
      if (gymSub === "gym_only" && ex.equipment !== "gym") return false;
      if (gymSub === "dumbbell" && ex.equipment !== "dumbbell") return false;
      if (gymSub === "all_gym" && ex.equipment !== "gym" && ex.equipment !== "dumbbell") return false;
    } else if (mode === "workout") {
      if (workoutSub === "bodyweight_only" && ex.equipment !== "bodyweight") return false;
      if (workoutSub === "with_dumbbell" && ex.equipment !== "bodyweight" && ex.equipment !== "dumbbell") return false;
    }

    if (muscleGroup && ex.muscle_group !== muscleGroup) return false;
    if (difficulty !== "all" && String(ex.difficulty) !== difficulty) return false;

    if (q) {
      const mLabel = formatMuscleLabel(ex.muscle_group).toLowerCase();
      const pLabel = formatPatternLabel(ex.pattern).toLowerCase();
      const eqLabel = EQUIPMENT_META[ex.equipment]?.badge.toLowerCase() || "";
      const hay = `${ex.name} ${ex.code} ${ex.muscle_group} ${mLabel} ${ex.pattern} ${pLabel} ${eqLabel}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}
