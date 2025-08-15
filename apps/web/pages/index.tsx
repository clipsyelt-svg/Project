import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";

type Job = {
  id: string;
  url: string;
  status: string;
  created_at: string;
  finished_at: string | null;
};

type Clip = {
  id: string;
  job_id: string;
  idx: number;
  path: string;
  hook: string | null;
  created_at: string;
};

export default function Home() {
  const [url, setUrl] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [clips, setClips] = useState<Record<string, Clip[]>>({});
  const [loading, setLoading] = useState(false);

  async function fetchJobs() {
    const { data } = await supabase
      .from("jobs")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(20);
    setJobs((data as Job[]) || []);
  }

  async function fetchClips(jobId: string) {
    const { data } = await supabase
      .from("clips")
      .select("*")
      .eq("job_id", jobId)
      .order("idx", { ascending: true });
    setClips((prev) => ({ ...prev, [jobId]: (data as Clip[]) || [] }));
  }

  useEffect(() => {
    fetchJobs();
  }, []);

  return (
    <div style={{ maxWidth: 700, margin: "40px auto", fontFamily: "Inter, system-ui, Arial" }}>
      <h1>Stream Clipper (MVP)</h1>
      <p>Paste a Twitch/YouTube/Kick VOD URL. We’ll try to auto-make multiple 60s, vertical, captioned clips.</p>
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input
          type="url"
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          style={{ flex: 1, padding: 10, border: "1px solid #ccc", borderRadius: 6 }}
        />
        <button
          onClick={async () => {
            setLoading(true);
            const res = await fetch("/api/create", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ url }),
            });
            setLoading(false);
            if (res.ok) {
              setUrl("");
              fetchJobs();
              alert("Job created! Processing runs every ~10 minutes.");
            } else {
              alert("Invalid URL or server error.");
            }
          }}
          disabled={!url || loading}
          style={{
            padding: "10px 16px",
            borderRadius: 6,
            border: "none",
            background: "#111",
            color: "#fff",
            cursor: "pointer",
          }}
        >
          {loading ? "Creating..." : "Create Job"}
        </button>
      </div>

      <h2 style={{ marginTop: 32 }}>Recent Jobs</h2>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {jobs.map((j) => (
          <li key={j.id} style={{ border: "1px solid #eee", borderRadius: 8, padding: 16, marginTop: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <div style={{ maxWidth: "70%" }}>
                <div style={{ fontWeight: 600 }}>{j.url}</div>
                <div style={{ fontSize: 12, color: "#666" }}>
                  {new Date(j.created_at).toLocaleString()} • status: <b>{j.status}</b>
                </div>
              </div>
              <button
                onClick={() => fetchClips(j.id)}
                style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid #ddd", background: "#fafafa" }}
              >
                Load Clips
              </button>
            </div>

            {clips[j.id]?.length ? (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Clips</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {clips[j.id].map((c) => (
                    <div key={c.id} style={{ border: "1px solid #eee", borderRadius: 6, padding: 12 }}>
                      <div style={{ fontSize: 12, color: "#666" }}>#{c.idx}</div>
                      {c.hook ? <div style={{ fontWeight: 600, margin: "6px 0" }}>{c.hook}</div> : null}
                      <a
                        href={`${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/clips/${c.path}`}
                        target="_blank"
                      >
                        Download MP4
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
