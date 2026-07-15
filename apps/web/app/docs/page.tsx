import { redirect } from "next/navigation";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function ApiDocsRedirect() {
  redirect(`${apiBase}/docs`);
}
