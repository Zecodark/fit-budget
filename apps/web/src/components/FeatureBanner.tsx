import type { ReactNode } from "react";
import { Dumbbell, Flame, Utensils } from "lucide-react";
import { MotionScene } from "@/components/MotionScene";

export function FeatureBanner({ kind, title, children }: {
  kind: "strength" | "nutrition" | "meals";
  title: string;
  children: ReactNode;
}) {
  const Icon = kind === "strength" ? Dumbbell : kind === "meals" ? Utensils : Flame;
  return (
    <div className="feature-banner">
      <MotionScene kind={kind === "strength" ? "strength" : "nutrition"} />
      <div className="feature-copy">
        <span className="quick-icon"><Icon size={19} /></span>
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
    </div>
  );
}

