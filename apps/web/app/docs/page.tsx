import { redirect } from "next/navigation";

import { apiDocsUrl } from "@/lib/api-config";

export default function ApiDocsRedirect() {
  redirect(apiDocsUrl());
}
