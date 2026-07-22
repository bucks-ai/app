# bucks.ai — Strategy & Doctrine

**Date:** 2026-07-11 · **Status:** living document · **Read with:** `BUCKS_AI_MASTER_ANALYSIS.md` (progress truth, §13 log) and `CHAT_HANDOFF_2026-07-11.md` (session continuity).

This is the *how bucks.ai thinks* document. The planner and every mission should build toward it. It is doctrine, not a task list — but it directly shapes what gets seeded next. Weak ideas were deliberately excluded to keep the system uncontaminated (see §7 for what was rejected and why).

---

## 1. THE ONE-LINE THESIS

**Sell convenience and completeness, not novelty.** Everything already has a tool; almost nothing has the *whole pipeline made effortless*. bucks.ai wins by collapsing "idea → live, owned, revenue-capable business" into the fewest possible human actions. Convenience is the product. After the first "wow," convenience is the reason people pay.

## 2. THE CONVENIENCE DOCTRINE (the core principle everything else descends from)

**"External containment enables convenience."** The more rigorously each grant of access is scoped, sandboxed, and revocable, the more you can safely automate on top of it. This resolves the apparent tension between "automate everything" and "stay secure/legal": you don't earn convenience by taking more trust (passwords, unfettered access) — you earn it by making each unit of trust *small and revocable* (OAuth scopes, per-business sandboxes, secret-names-not-values), which is precisely what makes it safe to build heavy automation on top.

Two operating laws fall out of this:

- **Law of minimal interruption.** bucks.ai interrupts the human at exactly two kinds of moments: (1) legal/identity/payment gates only a human can legally clear, and (2) irreversible or over-budget decisions. *Everything else has a sensible default and is done silently.* The moment you add a sixth "quick question," you've broken the magic. Defaults over questions, always.
- **Law of ownership.** What a user builds is genuinely theirs — real deployed app, their code, their accounts, portable, not held hostage. This is the anti-Lovable stance (see §5).

## 3. THE ACCOUNT / PROVISIONING MODEL (parent-child; why the user sets up almost nothing)

The customer does **not** sign up for the tool stack. bucks.ai (the company) owns master accounts once; every customer business is a **scoped child resource** provisioned under them via API. The 30-minute PostHog signup happens once ever — for bucks.ai, not per user.

Tools split three ways:

- **Type A — official provisioning API; one master account → unlimited API-created children, zero human, zero signups:** GitHub, Vercel, Supabase, Cloudflare (incl. domain registrar API), Stripe (Connect), Upstash; and the metered-key providers (OpenAI, Anthropic, Firecrawl, Apollo) where bucks.ai holds one org key and meters per business.
- **Type B — no account-creation API, but create parent org once → API-create children under it:** PostHog, Sentry, Resend, Clerk, Inngest/Trigger.dev, Notion/Airtable.
- **Type C — genuinely human, unautomatable by anyone (legal, not technical):** Stripe identity/bank verification, Apple/Google developer identity, entity filing, domain purchase over a budget cap. Convenience play = pre-fill everything, surface ONLY the legal core in one embedded screen inside the bucks.ai interface (the Stripe Connect hosted-onboarding pattern).

**Two buckets of tools from the user's view:**
1. **Invisible platform plumbing (bucks.ai's own accounts, user never sees):** PostHog, Sentry, the AI models, email, background jobs, rate-limit stores. The user's business gets a metered child; they no more need to own these than a Spotify listener needs to own AWS.
2. **Own-it tools the user connects (only to keep the output):** GitHub (their code), Vercel (their hosting), Cloudflare (their domain), Supabase (their data), Stripe (their money). ~5 OAuth connects, and even these are optional on the free/test run.

**Do NOT** build a system that scripts signups against anti-abuse/CAPTCHA/email-verification, or that stores user passwords, or that reads user inboxes to intercept verification emails. All three are fragile (break constantly), get IPs/domains/accounts banned, violate ToS, and — critically — are made *unnecessary* by the parent-child model, which has no signups to evade. OAuth + scoped tokens + a vault (Infisical/Doppler, storing secret *names*) delivers ~90% of the convenience at low risk; the password-vault version buys ~5% more for company-ending breach exposure. Always take the 90%.

## 4. THE TARGET USER EXPERIENCE (canonical; every mission builds toward this)

Persona: indie founder, heard about bucks.ai from a friend.

- **Phase 1 — Test (target <2 min to "it's building"):** sign up (1 screen, email or one-click Google), type one sentence describing the business, hit go. **Zero external account setup.** All infra provisioned as children under bucks.ai's master accounts, invisibly.
- **Phase 2 — The wow:** the node-graph UI animates (Blueprint → Scaffold → Build → Verify → Deploy), live event feed streaming; ~2-3 min later a real deployed app at `theirname.bucks.ai`. Working, shareable, from one sentence, zero config seen. This is the conversion moment — a real thing, not a demo.
- **Phase 3 — Upgrade:** enter a card (1 screen). They pay because they already saw it work; the paywall is *after* value, never before.
- **Phase 4 — Make it theirs (the OAuth moment):** a single Connect screen lists the ~5 own-it accounts with a **"Connect all"** button that fires each provider's OAuth in sequence (GitHub tab → approve → auto-close → Vercel tab → …), a progress bar ("2 of 5 connected"). ~8 seconds each, ~2 min total, once. Never a password into bucks.ai; every grant scoped + revocable on the provider's own screen. bucks.ai then re-provisions the business onto their accounts automatically.
- **Phase 5 — The one human wall (payments):** Stripe Connect pre-fills all boilerplate; bucks.ai surfaces ONE embedded screen for the only legally-human parts — verify ID, add payout bank. ~2 min, once, unavoidable by law. This is the ONLY time bucks.ai comes to the user beyond the one sentence and the OAuth clicks.

**Friction ledger (the pitch in one glance):** test = 1 signup + 1 sentence, zero accounts. Upgrade = 1 card screen. Own it = ~5 one-click OAuths (~2 min once). Take payment = ID+bank in one embedded screen (~2 min once). Everything else — repos, DBs, analytics, deploys, domains, monitoring, the actual building — automatic and invisible.

**"Connect all" note:** OAuth is per-provider by law (each grant is on that company's servers) — do NOT fake a single "accept-all" token; that would mean brokering credentials in a way that breaks the revocable/scoped safety. The sequenced auto-advancing flow gives ~95% of the seamlessness with 100% of the safety.

## 5. MONETIZATION DOCTRINE — Spotify/ChatGPT/Claude, NOT Lovable

The failure mode to avoid: Lovable-style, where free output is never truly yours (can't deploy, can't own, can't watch it succeed). That converts through *resentment* and caps at the desperate.

The model to build: free is **limited in QUANTITY, never crippled in OWNERSHIP.**
- **Free tier:** build real businesses that are genuinely yours — real deployed app, connect your own accounts, own the code, take it live, walk away *with* your repo anytime. Limited by *volume*: ~1 active business, bucks.ai subdomain unless a domain is brought, monthly build/agent-run caps, standard queue. Marketing line: *"On bucks.ai free, what you build is actually yours."*
- **Paid tier (the "why would I not"):** multiple concurrent businesses, custom domains handled, the full autonomous operator running unattended (the babysitter loop working your business while you sleep), priority/parallel execution, outreach + CRM + revenue tooling, cross-business memory/learning, higher caps. The pitch is "one thing → a portfolio on autopilot," a Spotify-grade different-life upgrade, not "unlock what we held hostage."

Why it converts better: demonstrated-value upgrades (a large, sticky population who already love a real free product) beat resentment upgrades (a small desperate one). This is why ChatGPT/Spotify/Claude subs feel un-second-guessable.

**Economics caveat (tune with M3 analytics):** free users cost real AI/infra COGS. Set the free *quantity* cap where a free user is cheap enough to carry — they are marketing + failure-learning training data — while paid clearly funds itself. Watch free→paid conversion and cost-per-free-user; move the caps to where the math works. Philosophy is fixed; the dial is data-driven.

## 6. MARKET-SELECTION & BUILDING DOCTRINE

### 6.1 The Market Selection Algorithm (how bucks.ai decides what to build — the anti-random-idea system)

This is the answer to "a good-sounding idea ≠ a money-making idea." An idea may enter the pipeline ONLY with demand evidence attached; brainstormed ideas with no evidence are rejected at the door. Four laws, then a four-step algorithm. Run manually by the founder for M5; encoded as the **Market Radar** mission later (§7) so bucks.ai proposes and the human approves.

**This section is executable doctrine, not prose.** It is wired into code in three places: (1) the planner ingests this file as context so every mission plan is doctrine-shaped (M4c task); (2) the mission compiler applies the building playbooks by default (M4d); (3) Market Radar (M7.5) encodes the sourcing + scoring + validation ladder below as running code. A doc the machine reads and obeys IS the code path — the doc form is what lets the founder audit and amend the brain in one place.

**Canon distillation (Graham "How to Get Startup Ideas" + YC/Caldwell tarpit corpus — reviewed 2026-07-21):**
- **Wells, not craters.** Build what a *small* group needs *urgently*, never what a large group wants mildly. Test: "who wants this so much they'll use a crappy v1 from a company they've never heard of?" No specific answer = bad idea. (Encoded in criteria 1 & 3.)
- **Plausible-sounding is the enemy.** Made-up "sitcom" ideas (social network for pet owners) draw "yeah, maybe I'd use that" from everyone and actual usage from no one. Politeness is not demand — only urgent need and payment are. (This is WHY the evidence-at-the-door rule exists.)
- **Notice, don't think up.** Good ideas are *noticed* gaps hitting a prepared mind, not brainstormed. bucks.ai's version of "noticing": mine observed complaints and observed spend at scale — pain mining is mechanized noticing. (Encoded in Step 1.)
- **Run TOWARD schleps and unsexy problems.** Tedious, messy, boring B2B problems (Stripe and payments) are systematically under-picked, so they're where value sits unclaimed. bucks.ai has no boredom and no schlep-fear — this is a structural edge; weight criterion 7 accordingly: unsexy = bonus, sexy-sounding = scrutiny.
- **Crowded market + a thesis = green; empty market = red.** Startups are almost never killed by competitors; err toward markets WITH competitors and unhappy customers, armed with a specific claim about what incumbents overlook. (Encoded in Law 4.)
- **Sell before you build** (Buchheit): trying to sell a bad idea surfaces the real one. Hence the pre-sell rung of the validation ladder is mandatory, not optional.
- **Tarpits are inverted signals** (Caldwell): ideas that occur to everyone, sound novel, and feel unclaimed (local events, restaurant discovery, generic "AI for X") are unclaimed because a graveyard of startups already died there. Popularity of an idea among founders is negative evidence.

**The four laws:**
1. **Markets over ideas.** Pick a starving crowd, then feed it. A mediocre product in a desperate market beats a great product in an indifferent one.
2. **Demand evidence over intuition.** Every candidate must trace back to *observed complaints* + *observed spend*. "People need this" is not evidence; people paying for a worse version of it is.
3. **Distribution before build.** The scarce resource is reachable buyers, not code (bucks.ai makes code ~free, which makes this law MORE binding, not less). If you can't name the channel and ~50 prospects before building, don't build.
4. **Competition is validation.** An empty market usually means no demand, not an opportunity. Look for crowded markets with visibly unhappy customers, not blue oceans.

**Step 1 — Source candidates from demand signals, never from brainstorming:**
- **Pain mining:** unprompted complaints in niche communities (Reddit, Indie Hackers, HN, trade forums, G2/Capterra 1-3★ reviews). Highest-value signals: "I wish / why doesn't X" phrasing, and complaints that recur for *years* with no good answer (time-validated, underserved).
- **Existing-spend signals:** people paying agencies/freelancers/clunky tools for the job today. The spend proves the market; bucks.ai just collapses the cost.
- **Manual-workaround signal:** users burning 5–10 hrs/week on spreadsheet-and-duct-tape workflows — that pain converts directly to ~$49–199/mo willingness to pay.
- **Event-triggered urgency:** buyers who self-identify publicly at a moment of pain (got breached, got a Google penalty, lost Stripe access). These are the easiest buyers on earth to find and time.

**Step 2 — Score every candidate 1–5 on seven criteria; any hard-fail kills it:**
| # | Criterion | Hard fail |
|---|---|---|
| 1 | Pain urgency (painkiller, ideally event-triggered) | Vitamin / nice-to-have |
| 2 | Evidence of existing spend | Nobody pays for any version today |
| 3 | Reachable buyers (nameable channel + ~50 named prospects) | "Everyone" / no channel |
| 4 | Buildable by the engine today (fits the M4b pipeline) | Needs capability we don't have |
| 5 | B2B price point ≥ $50/mo or ≥ $500 one-time | Consumer-cheap; volume math needs thousands of users |
| 6 | Time-to-value in days (demo-able fast) | Long onboarding before any wow |
| 7 | Tarpit filter (specific user in mind) | Consumer-social, local-events, generic AI wrapper, "platform for X" |

**Step 3 — Validation ladder BEFORE full build (spend-capped, ~2 weeks max):**
1. Landing page + small traffic test (paid or community): email-signup conversion ≥10% = real, ≥20% = strong.
2. 10 buyer conversations (or direct engagement in the complaint threads the idea came from). Listen for "must have," not "interesting."
3. **Pre-sell or concierge:** charge before the product fully exists (paid pilot, deposit, founding-member price). ~3 of 10 trials converting to *paid* = green-light. **Payment is the only real validation signal; interest, compliments, and signups are not.**

**Step 4 — Kill gates (feeds M8 memory):** no traction signal by a pre-set date, negative unit economics, or channel doesn't respond → kill, write the lesson down, next candidate. Volume + memory beat conviction; killing fast is a feature of the system, not a failure.

### 6.2 ICP & playbooks

- **First ICP:** AI automation agency owners + serious solo/indie AI-SaaS founders (18–35, some money, hate execution grunt work). NOT: nontechnical idea people, broke students, enterprises, regulated industries.
- **What to build first (M5 wedge):** a B2B micro-SaaS painkiller with reachable buyers and small scope. **CONFIRMED first test business (founder decision 2026-07-21): the security-hardening sprint service** — it scores clean on all seven §6.1 criteria: urgent event-triggered painkiller, buyers self-identify publicly (they post when breached), existing spend proven (security consultants charge $5-15k for this), demos the engine on someone else's repo (= exactly what M4b enables), and bucks.ai already owns the hardening playbook (M1: auth/zod/rate-limits/RLS/headers/route-inventory test). It must still pass the §6.1 Step-3 validation ladder before full build.
- **Kill criteria (feeds M8):** abandon a business on data — no traction signal by a set threshold, negative unit economics, no reachable buyers. Volume + memory beat conviction.
- **Building playbooks:** M1 hardening template applied to every launch (hardened-by-default is a differentiator), analytics-by-default (M3), the standard scaffold, deploy + smoke-check by default.
- **Endgame doctrine:** bucks.ai generates the idea via its specialized strategy and the human just approves. The doctrine in this file *is* the proposal engine. This is why the doctrine had to be written before that capability is built.
- **Cross-user learning ethics:** learning from all users' failures/successes is the long-term moat (M8) — but needs consent in terms + anonymization/aggregation from the first customer. "We learned from your failed business" is a feature when disclosed, a scandal when discovered.

## 7. IDEAS LEDGER — what's IN (strong) and what was REJECTED (to keep the system uncontaminated)

**IN — strong, sequenced into the roadmap:**
- Codified strategy/doctrine (this document) + the **Market Selection Algorithm (§6.1)** — the anti-random-idea system that decides what bucks.ai builds.
- **Market Radar** (automated §6.1: pain-mining scrapers + scoring + ranked opportunity briefs for human approval) — post-M5, once one manual pass has proven the rubric.
- Security-hardening: (a) hardening-by-default baked into every business scaffold (mission compiler applies the M1 playbook to every build), and (b) the hardening sprint service = **confirmed first test business for M5**.
- Provisioning & Credential Broker (the wizard, done right — parent-child + OAuth + vault). Post-M5.
- Node-graph operator UI. M5-era.
- **Loop babysitter — promoted to IMMEDIATE (own mission, M4c, next seed after M4b).** Auto-restart unless hard-blocked on a human gate; **plan-level approval + auto-seeding** (founder approves the whole roadmap ONCE; the babysitter seeds and chains every approved mission itself — per-mission seeding is abolished as an unnecessary gate); limits-aware pause/resume (rate/budget exhaustion → wait out the window and resume, don't die); heartbeat/stall detection. Rationale: the founder is currently the babysitter — the single biggest throughput bottleneck in the whole system. Human gates that remain: SQL approvals, resource/credential gates, budget caps, unplanned missions.
- Learn-from-failures memory (M8), with the consent guardrail.
- Spotify-not-Lovable free/paid tiering (this document, §5).
- TikTok/IG-video → build, as a FEATURE (intake modality) and marketing engine — post-M5, low cost.

**REJECTED — deliberately excluded so they don't poison the system:**
- Mass side-hustle spray *as a revenue strategy* — negative-cashflow lottery thinking; distribution, not building, is the scarce resource. (Kept ONLY as 3-5 capped shakedown launches for pipeline testing + failure data.)
- Build-to-app-store as a near-term product — blocked by Apple/Google human identity+review (Type-C); future SKU at best.
- Auto-file patents — regulated legal practice, low ICP value, per-filing cost. Killed entirely.
- Password-vault / inbox-interception / signup-scripting convenience — unnecessary under parent-child, and company-ending risk.

## 8. THE ROAD TO SUCCESS (arc + the one metric)

- **Now–1mo:** finish M4b (machine can build businesses that aren't itself) → **M4c babysitter (small, immediate: the loop stops needing the founder)** → **M4d hardened-by-default scaffold (small)** → §6.1 algorithm run manually gates M5 selection.
- **1–3mo:** launch ONE real business (M5), start founder sales immediately (manual outreach + system-drafted messages, don't wait for M6), publish build-in-public proof from the run corpus; add outreach (M6) + Stripe revenue loop (M7). Aim: first paying users, $10-50k traction.
- **~mo 4 (YC app):** written around verifiable numbers — "system created N repos, deployed N apps, configured N tools, sent N compliant emails, booked N demos, closed $X, humans only for legal/payment/calls."
- **Post-proof (portfolio era):** M8 memory → cross-business playbooks; full Provisioning Broker + wizard; node-graph UI; N concurrent businesses; Marketing Brain (content/SEO/ads, hard external budget caps); self-serve product.
- **Honest ceiling:** the machine makes attempts cheap and compounding; whether any reaches $1M/yr depends on problem selection + distribution + market, which no code fixes — volume + memory improve the odds. **The most likely million-dollar business bucks.ai produces is bucks.ai itself.**
- **The one metric to obsess over:** time from "click Execute / customer says yes" to deployed product. Everything that shortens it raises both capacity and the story.
