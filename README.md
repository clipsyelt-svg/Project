\# Stream Clipper (Free MVP)



Paste a VOD URL → automatically produce multiple 60s 9:16 captioned clips.  

Free tiers: Vercel (web), Supabase (DB+storage), GitHub Actions (worker).



\## 1) Supabase (DB + Storage)



\- Create project → Settings → `Project URL` and `Anon` key (copy).

\- Storage → create bucket `clips`. Make it \*\*Public\*\* (or use signed URLs and update the UI link).

\- SQL editor → run:



```sql

create extension if not exists pgcrypto;



create table if not exists jobs (

&nbsp; id uuid primary key default gen\_random\_uuid(),

&nbsp; url text not null,

&nbsp; status text not null default 'pending',

&nbsp; created\_at timestamptz default now(),

&nbsp; finished\_at timestamptz

);



create table if not exists clips (

&nbsp; id uuid primary key default gen\_random\_uuid(),

&nbsp; job\_id uuid references jobs(id) on delete cascade,

&nbsp; idx int,

&nbsp; path text,

&nbsp; hook text,

&nbsp; created\_at timestamptz default now()

);



