import { Suspense } from "react";
import { SmartRedirectClient } from "@/components/SmartRedirectClient";

export default function GoHandlePage({
  params,
}: PageProps<"/go/[handle]">) {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-zinc-950 text-zinc-300 flex items-center justify-center text-sm">
          Đang kết nối tới ứng dụng YouTube...
        </div>
      }
    >
      {params.then(({ handle }) => (
        <SmartRedirectClient rawHandle={handle} />
      ))}
    </Suspense>
  );
}
