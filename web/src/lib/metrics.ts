export type MetricSpec = { label: string; unit: string; decimals: number; lowerIsBetter?: boolean };

/** Display names for the normalized metric keys the API stores. */
export const METRICS: Record<string, MetricSpec> = {
  weight: { label: "Weight", unit: "kg", decimals: 1 },
  fat_ratio: { label: "Body fat", unit: "%", decimals: 1, lowerIsBetter: true },
  fat_mass: { label: "Fat mass", unit: "kg", decimals: 1, lowerIsBetter: true },
  fat_free_mass: { label: "Fat-free mass", unit: "kg", decimals: 1, lowerIsBetter: false },
  muscle_mass: { label: "Muscle mass", unit: "kg", decimals: 1, lowerIsBetter: false },
  bone_mass: { label: "Bone mass", unit: "kg", decimals: 1 },
  hydration: { label: "Hydration", unit: "kg", decimals: 1 },
  bmi: { label: "BMI", unit: "", decimals: 1 },

  kcal_in: { label: "Energy in", unit: "kcal", decimals: 0 },
  protein_g: { label: "Protein", unit: "g", decimals: 0 },
  carbs_g: { label: "Carbs", unit: "g", decimals: 0 },
  fat_g: { label: "Fat", unit: "g", decimals: 0 },

  steps: { label: "Steps", unit: "", decimals: 0 },
  active_kcal: { label: "Active energy", unit: "kcal", decimals: 0 },
  basal_kcal: { label: "Basal energy", unit: "kcal", decimals: 0 },
  exercise_min: { label: "Exercise", unit: "min", decimals: 0 },
  distance_km: { label: "Distance", unit: "km", decimals: 1 },
  vo2max: { label: "VO₂ max", unit: "ml/kg/min", decimals: 1, lowerIsBetter: false },

  resting_hr: { label: "Resting HR", unit: "bpm", decimals: 0, lowerIsBetter: true },
  heart_rate: { label: "Heart rate", unit: "bpm", decimals: 0 },
  hrv: { label: "HRV (SDNN)", unit: "ms", decimals: 0, lowerIsBetter: false },
  spo2: { label: "SpO₂", unit: "%", decimals: 0, lowerIsBetter: false },
  body_temp: { label: "Body temperature", unit: "°C", decimals: 1 },
  systolic_bp: { label: "Systolic BP", unit: "mmHg", decimals: 0 },
  diastolic_bp: { label: "Diastolic BP", unit: "mmHg", decimals: 0 },
};

export const spec = (metric: string): MetricSpec =>
  METRICS[metric] ?? { label: metric.replaceAll("_", " "), unit: "", decimals: 1 };

export const format = (metric: string, value: number) => {
  const { unit, decimals } = spec(metric);
  const n = value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return unit ? `${n} ${unit}` : n;
};

/**
 * Is this rate of change the direction the user wants?
 * null when the metric has no better direction — steps and heart rate aren't goals.
 */
export const favourable = (metric: string, perWeekValue: number): boolean | null => {
  const { lowerIsBetter } = spec(metric);
  if (lowerIsBetter === undefined || perWeekValue === 0) return null;
  return lowerIsBetter ? perWeekValue < 0 : perWeekValue > 0;
};

/** Rate of change, signed and rounded for display. The API sends 3 decimals. */
export const perWeek = (metric: string, value: number) => {
  const { unit } = spec(metric);
  const n = Math.abs(value) >= 10 ? Math.round(value) : Number(value.toFixed(2));
  return `${n > 0 ? "+" : ""}${n} ${unit || ""}`.trim();
};

export const PAGES = {
  body: ["weight", "fat_ratio", "muscle_mass", "fat_mass", "fat_free_mass", "hydration", "bone_mass", "bmi"],
  nutrition: ["kcal_in", "protein_g", "carbs_g", "fat_g"],
  training: ["steps", "active_kcal", "exercise_min", "distance_km", "vo2max"],
  recovery: ["resting_hr", "hrv", "spo2", "heart_rate", "body_temp"],
};
