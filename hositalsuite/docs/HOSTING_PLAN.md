# Hosting plan — what to buy, from whom, and how to move
**GENERAL HOSPITAL IJEDE** · 19 August 2026

---

## The headline, before the detail

I measured your app rather than guessing. **Your load test already proved it
handles 4,000 requests per minute on ONE worker with 0% failures**, and it only
started to strain at ~8,800/min.

Here is what your user numbers actually mean:

| Users/day | Busiest hour | Requests/min at peak | vs what you already survive |
|---|---|---|---|
| 5,000 | 1,750 | ~730 | **18%** |
| 10,000 | 3,500 | ~1,460 | **36%** |
| 15,000 | 5,250 | ~2,190 | **55%** |
| 25,000 | 8,750 | ~3,650 | **91%** |

**Even 25,000 users a day is inside what your app has already been measured
doing on a single small server.** You do not need a big expensive machine. You
need a *reliable* one, with a proper database and real backups.

I have sized everything with roughly 3× headroom anyway, because hospital
traffic is spiky and a queue at 8am is not the moment to discover you were
optimistic.

---

## 1. What type of hosting — and the honest recommendation

**Buy a VPS (a virtual private server) in a Lagos data centre.** Not shared
hosting, not a dedicated machine.

| Type | Verdict |
|---|---|
| Shared hosting (₦2,000–5,000/mo) | ❌ **No.** Cannot run Python properly, no root access, no PostgreSQL. It is built for WordPress |
| **VPS** | ✅ **Yes.** Full control, real PostgreSQL, sensible price |
| Dedicated server | ❌ Overkill at these numbers. You would pay 5× for capacity you cannot use |
| Staying on Render | ⚠️ Works, but see the honest note below |

### The honest note about leaving Render

Render is currently doing the job. Before you move, be clear *why* you are
moving, because a migration always costs a weekend and some risk.

**Good reasons to move to Nigeria:**
- **The law is tightening.** Health data is *sensitive personal data* under the
  NDPA 2023, and NITDA's data-classification framework pushes health data
  towards local hosting. This is not yet a blanket legal requirement — but for
  a **Lagos State government hospital** it is where the wind is blowing.
- **Speed for your users.** Frankfurt (your current region) is ~200ms away.
  Lagos is ~10–20ms. Every page will feel snappier on hospital wifi.
- **Payment in naira**, no card in dollars, no FX surprises.
- **Local support** who answer the phone in your timezone.

**Good reasons to stay a little longer:**
- Render's free tier is genuinely working
- Migration takes a weekend and carries real risk
- Nigerian providers vary wildly in quality

**My advice: move when you have your first paying hospital, not before.**

---

## 2. What to buy at each size

I have sized these against your **measured** performance, with headroom.

### 5,000 users/day
| | Spec |
|---|---|
| **CPU** | 2 vCPU |
| **RAM** | 4 GB |
| **Storage** | 100 GB NVMe SSD |
| **Database** | PostgreSQL on the same server |
| **Why** | Peak load ~18% of proven capacity. Data grows ~3 GB/year |

### 10,000 users/day
| | Spec |
|---|---|
| **CPU** | 4 vCPU |
| **RAM** | 8 GB |
| **Storage** | 200 GB NVMe SSD |
| **Database** | PostgreSQL same server, or its own small VPS |
| **Why** | ~36% of proven capacity. Data ~6 GB/year |

### 15,000 users/day
| | Spec |
|---|---|
| **CPU** | 6 vCPU |
| **RAM** | 12 GB |
| **Storage** | 300 GB NVMe SSD |
| **Database** | **Separate database server** from here on |
| **Why** | ~55% of capacity. Splitting the database is what buys the next 3× |

### 25,000 users/day
| | Spec |
|---|---|
| **App server** | 8 vCPU, 16 GB RAM, 200 GB |
| **Database server** | 4 vCPU, 8 GB RAM, 300 GB |
| **Why** | ~91% of single-worker capacity — this is where you split the two |

> ⚠️ **A code change is needed at 15,000+.** Your app runs **one worker**
> because the scheduler (reminders, SLA escalation, backups) must run exactly
> once. To use more than one worker you set `DISABLE_SCHEDULER=1` on the extra
> workers. It is a small change, already documented in your README, and I can
> do it in an afternoon when you need it.

### Storage: how fast your data actually grows

| Users/day | Database growth |
|---|---|
| 5,000 | ~2.7 GB/year |
| 10,000 | ~5.5 GB/year |
| 15,000 | ~8.2 GB/year |
| 25,000 | ~13.7 GB/year |

Modest — because you wisely refused to become an EMR. No scans, no images.
Add ~30% for PDFs and backups.

**Always choose NVMe SSD over SATA.** It is the single biggest speed difference
for a database, and usually costs very little more.

---

## 3. Which Nigerian company

Prices are what providers advertised as of August 2026 — **confirm before you
pay**, they move.

### 🥇 First choice: WhoGoHost / GO54

The best-known Nigerian host, locally hosted, transparent naira pricing.

| Your size | Plan | Spec | Price |
|---|---|---|---|
| 5,000/day | **C4** | 2 vCPU, 4 GB, 100 GB SSD | **₦36,550/mo** |
| 10,000/day | **C5** | 4 vCPU, 8 GB, 200 GB SSD | **₦73,100/mo** |
| 15,000/day | **C6** | 6 vCPU, 12 GB, 300 GB SSD | **₦109,650/mo** |
| 25,000/day | **C7** + **C5** | 8 vCPU/16 GB + database server | **₦219,300/mo** |

### 🥈 Worth a quote: Layer3, MainOne/Equinix, Galaxy Backbone

These are **carrier-grade Nigerian data centres**. They do not publish prices —
you ring them. For a **Lagos State government hospital** they are the right
conversation, because they understand government procurement and can give you
a written data-residency statement, which matters for NDPA compliance.

**Ask for:** a Lagos-hosted VPS, NVMe, daily backups, and an uptime SLA.

### ⚠️ Cheaper options — be careful

Nairahost advertises ₦7,500/mo for 2 GB RAM, and Truehost/QServers are also
cheap. For a personal website, fine. **For a hospital, ask three questions
before you pay anyone:**

1. **Where is the server physically?** (Some "Nigerian" hosts resell European
   servers — you get the price but none of the data-residency benefit)
2. **What is the uptime SLA, in writing?**
3. **Do you take daily off-server backups?**

If they cannot answer all three clearly, walk away. A hospital cannot be down.

---

## 4. Total monthly cost, realistically

| Users/day | Server(s) | Backups | Domain/SSL | **Total** |
|---|---|---|---|---|
| 5,000 | ₦36,550 | ₦5,000 | ₦1,500 | **~₦43,000** |
| 10,000 | ₦73,100 | ₦8,000 | ₦1,500 | **~₦83,000** |
| 15,000 | ₦109,650 | ₦12,000 | ₦1,500 | **~₦123,000** |
| 25,000 | ₦219,300 | ₦20,000 | ₦1,500 | **~₦241,000** |

Add the messaging costs from your other guide (~₦10,000/mo SMS at 100
patients/day).

**Never skip the backup line.** Your app takes its own backups, but they live
on the same machine. If that machine dies you lose both. Off-server backup is
the cheapest insurance you will ever buy.

---

## 5. On the law — what actually applies to you

I looked this up rather than guessing, and the honest position is nuanced:

- **There is NO blanket law** requiring all Nigerian data to stay in Nigeria.
  Anyone who tells you otherwise is oversimplifying.
- **BUT** health data is explicitly **sensitive personal data** under the
  NDPA 2023, and the NDPC expects a stronger justification before it leaves
  the country.
- **AND** NITDA's cloud policy pushes government data towards local hosting.
  You are a **Lagos State government hospital**.
- **The National Health Act 2014** adds its own confidentiality duties.

**Practical translation:** you are probably not breaking any law today on
Render. But hosting in Lagos removes the question entirely, and for a
government hospital that is worth real money in a procurement conversation.

**Whatever you do, you need:** a written record of where data lives, a Data
Protection Officer named, and a tested restore. You already have the audit
trail and the backups — that puts you ahead of most.

---

## 6. How to migrate — the good news

**Your app is unusually easy to move**, for three reasons I can point at:

1. **You have a Dockerfile.** The whole app is one container.
2. **Uploads and PDFs are already IN the database** (`STORAGE_BACKEND=db`) —
   that decision, made months ago after Render wiped your files, means there
   are no loose files to move.
3. **Alembic migrations run at boot**, so the new database builds itself.

### The plan — one Saturday morning

**The week before**
1. Buy the VPS. Ask for **Ubuntu 24.04 LTS**.
2. Install Docker, PostgreSQL 17, Nginx, and Certbot for SSL.
3. Point a **staging** subdomain at it (`test.yourhospital.ng`).
4. Restore a copy of your Supabase data there and **run the app for a week**
   on real data with nobody using it.

**Saturday, 7am — the actual move (about 90 minutes)**

```bash
# 1. Put the live site into read-only, or accept ~30 minutes of downtime
#    (a Saturday morning is the quietest window a hospital has)

# 2. Take a final copy of everything from Supabase
pg_dump "postgresql://postgres.YOURPROJECTREF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require" \
  --no-owner --no-privileges -Fc -f ghijede-final.dump

# 3. Load it into the new Lagos database
createdb -U postgres hospitalsuite
pg_restore -U postgres -d hospitalsuite --no-owner ghijede-final.dump

# 4. Get the code
git clone https://github.com/Hcarepro2026/hositalsuite.git
cd hositalsuite

# 5. Set the environment (same names as Render — nothing new to learn)
cat > .env <<'ENV'
DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/hospitalsuite
SECRET_KEY=<generate a new one>
STORAGE_BACKEND=db
COOKIE_SECURE=1
TRUSTED_PROXY_COUNT=1
TIMEZONE=Africa/Lagos
GROQ_API_KEY=...
TERMII_API_KEY=...
ENV

# 6. Start it
docker build -t hospitalsuite .
docker run -d --name hs --env-file .env -p 8077:8077 --restart always hospitalsuite

# 7. Prove it works BEFORE switching the domain
curl http://localhost:8077/api/v1/ready     # must say {"ready":true}
```

**8. Only when `ready:true`,** point your domain at the new server and run
Certbot for HTTPS.

**9. Leave Render running for two weeks.** It costs nothing and it is your
undo button.

### The three things that will bite you

1. **The database password.** Yours contains `@`, which must be written `%40`
   in the connection string. This has already caught you once.
2. **HTTPS.** Render did it for free. On your own VPS you run Certbot, and you
   must set up **auto-renewal** or the site breaks in 90 days.
3. **You now own the machine.** Security updates, disk space, restarts — nobody
   else is watching. Budget either a few hours a month, or ~₦20,000/mo for a
   managed plan where the host does it.

---

## 7. What I would actually do, in your position

**Today:** stay on Render. It is working, it is free, and you have no paying
customers to protect yet.

**When you sign your first paying hospital:** move to WhoGoHost **C4**
(₦36,550/mo). By then the monthly cost is a rounding error against the revenue,
and "your data is hosted in Lagos" becomes a selling point rather than a cost.

**Before you move:** get a written quote from **Layer3** and **MainOne**. For a
Lagos State government hospital, a carrier-grade Nigerian data centre with a
proper SLA may cost more but will open procurement doors that a ₦36,000 VPS
will not.

**The most important sentence in this document:** your app is not the
bottleneck. It handles 25,000 users a day on hardware costing ₦220,000/month.
Spend your energy on getting hospitals to use it, not on servers.
