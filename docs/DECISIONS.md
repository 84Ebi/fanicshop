# Decisions & open questions

## Clarifying questions (asked before implementation)

The brief asked for these to be confirmed first. The plan was approved with the defaults below
recorded here; **please correct any that are wrong** — changes are cheap before M2.

### 1. Currency — **assumed: display Toman, store Rial**
- Canonical DB unit: integer Rial (precision for unique payment suffixes).
- User-facing: Toman (`rial // 10`) with Persian digits; payment instructions show the exact
  Rial suffix so the transfer is identifiable.
- **Confirm:** do you want prices shown only in Toman (suffix shown separately) or as a single
  odd Rial amount?

### 2. Delivery process — **assumed: Iran-wide, address collected at checkout, manual handover**
- Customer saves address (province/city/line/postal code) and a delivery note at checkout.
- Admin marks `preparing → shipped/out_for_delivery → delivered`; customer confirms receipt.
- **Confirm:** do you deliver only in one city, use a courier service, or require delivery fee
  calculation by city? (Current fee is a flat admin-configurable value.)

### 3. Payment verification — **adopted: unique amount + forwarded bank SMS, receipt fallback**
- Automatic: HMAC-protected webhook receives forwarded bank SMS from an allow-listed device;
  regex parsers extract amount/reference; unique Rial suffix matches one intent.
- Fallback: customer uploads a receipt photo; admin approves/rejects manually.
- Rationale: card-to-card has no API; SMS forwarding is the only realistic automatic signal in
  Iran, and a human fallback is necessary for banks/phones that cannot forward.
- **Confirm:** can you run an always-on phone (or SMS gateway) that forwards bank SMS to our
  HTTPS endpoint? If not, we will run receipt-only until one is available.

### 4. Number of admins — **assumed: 1 owner + optional support admins**
- `ADMIN_IDS` allows multiple admins; `ADMIN_ROLES` maps `owner` / `support`.
- Support can verify users and manage orders but **cannot** touch money, broadcast or settings.
- **Confirm:** how many admins, and should any be restricted to support-only?

### 5. Hosting — **assumed: a VPS with Docker Compose, long polling for MVP**
- Long polling needs no public TLS endpoint and works behind any NAT.
- Webhook mode is supported via the same aiohttp app for production and for the SMS callback.
- Local Postgres binaries are available in this environment for tests; Docker daemon is not, so
  compose is validated syntactically here and end-to-end on the VPS.
- **Confirm:** will you host on a VPS (recommended) or a managed container platform?

## Other decisions

| # | Decision | Reason |
| --- | --- | --- |
| D1 | aiogram 3 over python-telegram-bot | Strong FSM, callback-keyboard ergonomics, active maintenance. |
| D2 | PostgreSQL only, no SQLite | Money ledger needs row locks, partial unique indexes and concurrent writers. |
| D3 | Product-agnostic engine, no cigar-specific text in code | Keeps the bot reusable; operator owns product naming and legal compliance. |
| D4 | 18+ self-declaration recorded with timestamp during signup | Mandatory gate; see legal notes. |
| D5 | Full card PAN only in env, never in DB or logs | Reduces breach impact. |
| D6 | Plan approved by user on 2026-11-24; implementation started from existing M0 skeleton | Server restarts had already produced M0 and part of M1; work continued, docs backfilled. |

## Security incident note

The bot token was pasted into the conversation on 2026-11-24. It must be treated as compromised:
revoke it in BotFather (`/revoke`) and place only the new token in the gitignored `.env`. It is
never written to source, docs or git history.

## Legal / policy risks (operator to decide)

- **Age-restricted goods:** 18+ self-declaration is implemented, but self-declaration is weak;
  consider additional verification if local law requires it.
- **Telegram policy:** selling regulated goods may violate Telegram ToS and can get the bot
  banned; review the ToS and your local rules before launch.
- **Local law:** online sale/delivery of tobacco products is restricted or prohibited in many
  jurisdictions, including possibly yours. Confirm legality, licensing, taxation, age checks at
  delivery, and advertising restrictions. You are responsible for compliance.
- **PII:** phone numbers and addresses are personal data; restrict access, define retention and
  deletion policy, and never commit user data.
- **Payments:** card-to-card is informal; refunds/chargebacks have no automated path and must be
  handled manually with an audit trail.
