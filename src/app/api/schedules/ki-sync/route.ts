import { handleSchedule } from "@vercel/schedules";
import { runAllDueKiChallengesSync } from "@/lib/ki-challenge-server";

export const maxDuration = 60;

export const POST = handleSchedule(async (metadata) => {
  const result = await runAllDueKiChallengesSync({ forceAll: false });
  console.log(
    `[ki-challenge-sync] ${metadata.name} exec=${metadata.executionId} checked=${result.checked} synced=${result.synced} errors=${result.errors.length}`
  );
  if (result.errors.length > 0) {
    console.warn("[ki-challenge-sync] errors:", result.errors.join(" | "));
  }
});
