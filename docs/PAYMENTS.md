# Card-to-card payment verification

## The problem

Iranian card-to-card transfers have **no public confirmation API**. The bot must decide whether
a customer really paid without access to bank statements. Three realistic mechanisms exist:

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Forwarded bank SMS, parsed automatically | Near-real-time, no customer effort, fully automated | Requires the seller's phone to forward SMS to our webhook; banks/phones vary; SMS may be delayed; depends on an always-on forwarder | **Primary** |
| Unique payment amount (Rial suffix) | No infrastructure; disambiguates transfers | Only helps when we can see the transfer (i.e. with SMS parsing); customer must pay the odd Rial amount exactly | **Required companion** to SMS |
| Receipt photo + manual admin approval | Works with zero automation; universal fallback | Admin workload, slower, social-engineering risk | **Fallback**, always available |

**Recommendation (adopted):** unique-amount intents + forwarded SMS as the automatic path,
with receipt-upload manual approval as the fallback. All paths write to the same append-only
payment ledger. Wallet top-ups use the identical mechanism.

## Payment intent

1. Customer chooses card-to-card (or a wallet+card split).
2. Service computes `card_part_rial = total_rial - wallet_used_rial`.
3. It allocates a random `suffix_rial` in `[SUFFIX_MIN_TOMAN*10, SUFFIX_MAX_TOMAN*10]` not
   currently used by a pending intent (partial unique index prevents collisions).
4. `amount_due_rial = card_part_rial + suffix_rial`; `expires_at = now + PAYMENT_WINDOW_MINUTES`.
5. Bot shows: destination card (from **env**, masked in logs), cardholder, exact amount
   (Toman + Rial suffix), deadline (Persian digits), and intent code.
6. Customer transfers, then either the SMS forwarder posts the bank SMS or the customer uploads
   a receipt.

## SMS ingestion

`POST /internal/sms` with:
- Header `X-SMS-Device-Id` — must be in `SMS_DEVICE_IDS`.
- Header `X-SMS-Signature` — HMAC-SHA256 of the raw body with `SMS_HMAC_SECRET`.
- JSON body: `{"device_id", "body", "received_at"}`.

Verification: constant-time HMAC compare, device allow-list, timestamp freshness (reject very old
messages), then parse. Raw body is stored only if `STORE_RAW_SMS=true` and is masked for phone
numbers/PANs before storage. Every request is logged without secrets.

Parsers: regex-based per Iranian bank pattern, extracting amount (Rial), reference/trace number,
and optionally sender card last-4. Unknown formats are stored as unparsed and alert admins if the
failure rate is high.

## Matching logic

Inside **one database transaction**:

1. Reject duplicate `reference` (unique index) → log `duplicate_sms`, no state change.
2. Find candidate pending intents where `amount_due_rial = amount_rial` and
   `expires_at > now`, ordered by `expires_at`, using `SELECT … FOR UPDATE SKIP LOCKED`.
3. If the amount equals a pending intent's `amount_due_rial`: mark it `matched`, write
   `bank_transaction.matched_intent_id`, credit wallet / mark order paid.
4. If several candidates match the same amount (should be prevented by unique suffix), do not
   guess: flag `ambiguous_match`, alert admins, require manual resolution.
5. If no candidate: check `expired` intents with the same amount → `late_payment` log and notify
   admins (they may manually credit). Otherwise `unmatched_payment` log.

## Edge cases

| Case | Handling |
| --- | --- |
| **Expired payment window** | Intent becomes `expired`; customer is told the code is void and given a fresh intent with a new suffix. Late SMS with old amount → `late_payment`, admin alert, manual approval only. |
| **Wrong amount** | No match → `unmatched_payment`. Admin sees it in the payment log; customer can be asked to pay exact amount. |
| **Partial amount** | Intent becomes `partial` with `paid_rial` recorded; the remaining balance gets a **new suffix** and intent, linked to the original. Order stays unpaid until complete. |
| **Duplicate payment / SMS** | Unique `reference` + matched-intent guard: second transfer is logged as `duplicate`, never credits twice; admin is alerted to arrange a refund. |
| **Two customers, same amount** | Unique suffix makes collision virtually impossible; if it still happens, matching refuses to guess and escalates. |
| **SMS delayed past 15 min** | `SMS_GRACE_MINUTES` window: a late-but-within-grace match is accepted with a `late_match` flag; beyond grace → manual approval. |
| **Receipt only** | Proof photo → `pending`; admin approves (credits) or rejects (with reason); both notify customer. |
| **Bank downtime / no forwarder** | Receipt fallback keeps the shop usable; admins get an alert when SMS ingestion has been silent too long. |

## Ledger rules

- A `bank_transaction` row is created for **every** inbound SMS (even unmatched).
- Every wallet change writes `wallet_transactions` with signed `delta_rial`, resulting
  `balance_after_rial`, `type` and `reason`.
- Order payment uses a transaction that updates `orders.wallet_paid_rial/card_paid_rial`,
  `payment_state`, `status`, and appends `order_status_history` atomically.
- Refunds are explicit, admin-only `refund` ledger entries; never silent deletions.

## Security

- Full destination PAN lives only in env; bot shows it to the customer on request but logs mask it.
- HMAC secret never logged; device allow-list; replay protection via reference uniqueness and
  timestamp freshness.
- Receipt images are stored as Telegram `file_id`, not downloaded bytes.
- Rate limits per user on intent creation and receipt uploads to prevent spam/DoS.
