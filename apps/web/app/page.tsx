import { QueryProvider } from "@/components/query-provider";
import { ControlCenter } from "@/features/access-requests/control-center";

export default function Home() {
  return (
    <QueryProvider>
      <ControlCenter />
    </QueryProvider>
  );
}

