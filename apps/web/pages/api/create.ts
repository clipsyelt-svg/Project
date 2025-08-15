import type { NextApiRequest, NextApiResponse } from "next";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

const VALID_HOSTS = ["youtube.com", "youtu.be", "twitch.tv", "kick.com"];

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") return res.status(405).end();
  const { url } = req.body || {};
  try {
    const u = new URL(url);
    if (!VALID_HOSTS.some((h) => u.hostname.includes(h))) {
      return res.status(400).json({ error: "Unsupported URL" });
    }
  } catch {
    return res.status(400).json({ error: "Invalid URL" });
  }

  const { error } = await supabase.from("jobs").insert({ url, status: "pending" });
  if (error) return res.status(500).json({ error: error.message });
  res.status(200).json({ ok: true });
}
