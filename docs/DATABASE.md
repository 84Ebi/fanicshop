# Database reference

Engine: PostgreSQL 16. All money columns are `BIGINT` **Rial**. Timestamps are timezone-aware
(`Asia/Tehran` presentation). Tables use the naming convention `ix_/uq_/ck_/fk_/pk_%…`.

## Identity

### `users`
`id` PK, `telegram_id` BIGINT UNIQUE, `username`, `tg_first_name`, `tg_last_name`,
`full_name` (required), `phone` (10-digit, partial unique), `age_confirmed_at`,
`status` ∈ `draft|pending|verified|rejected|blocked`, `rejection_reason`, `block_reason`,
`wallet_balance_rial` (>= 0), `bot_blocked_at`, `last_seen_at`, `created_at`, `updated_at`.

### `user_events` (append-only)
`id`, `user_id` FK, `event` ∈ `signup|age_confirm|submitted|approve|reject|block|unblock|phone_change`,
`from_status`, `to_status`, `actor_telegram_id`, `reason`, `created_at`.

### `addresses`
`id`, `user_id` FK, `receiver_name`, `receiver_phone`, `province`, `city`, `address_line`,
`postal_code`, `note`, `is_default`, `is_deleted`, timestamps. Partial unique index on
`(user_id)` where `is_default AND NOT is_deleted`.

## Catalog

### `categories`
`id`, `slug` UNIQUE, `title_fa`, `sort_order`, `is_active`, timestamps.

### `products`
`id`, `category_id` FK RESTRICT, `title_fa`, `description_fa`, `price_rial` > 0,
`stock_qty` >= 0, `reserved_qty` (0..stock_qty), `is_active`, `archived_at`, `sort_order`,
timestamps.

### `product_images`
`id`, `product_id` FK CASCADE, `telegram_file_id`, `sort_order`, timestamps. Bytes are never stored.

### `carts` / `cart_items`
`carts`: `id`, `user_id` FK UNIQUE, timestamps.
`cart_items`: `id`, `cart_id` FK CASCADE, `product_id` FK CASCADE, `qty` 1..20,
`price_at_add_rial`, timestamps; unique `(cart_id, product_id)`.

## Orders

### `orders`
`id`, `public_code` UNIQUE, `user_id` FK RESTRICT,
`status` ∈ `awaiting_payment|paid|preparing|shipped|out_for_delivery|delivered|cancelled|refunded`,
`payment_state` ∈ `unpaid|pending|partially_paid|paid|refunded`,
`subtotal_rial`, `delivery_fee_rial`, `discount_rial`, `total_rial` (= subtotal+fee-discount),
`wallet_paid_rial`, `card_paid_rial`, `address_snapshot` JSON, `delivery_note`, `admin_note`,
`shipped_at`, `delivered_at`, `customer_confirmed_at`, `cancelled_at`, `cancel_reason`, timestamps.

### `order_items` (immutable)
`id`, `order_id` FK CASCADE, `product_id` FK SET NULL, `title_snapshot`, `unit_price_rial`,
`qty` > 0, `line_total_rial` (= unit*qty), `created_at`.

### `order_status_history` (append-only)
`id`, `order_id` FK CASCADE, `from_status`, `to_status`, `source` ∈ `user|admin|system`,
`actor_telegram_id`, `note`, `created_at`.

## Payments

### `payment_intents`
`id`, `code` UNIQUE, `user_id` FK, `order_id` FK nullable, `kind` ∈ `order|topup`,
`target_rial`, `suffix_rial`, `amount_due_rial` (= target+suffix), `status` ∈
`pending|matched|partial|expired|failed|cancelled`, `paid_rial`, `expires_at`, `matched_at`,
timestamps. Unique partial index on `suffix_rial` where status is pending.

### `sms_messages` (append-only)
`id`, `device_id`, `hmac_ok`, `raw_body` (nullable, masked), `parsed_amount_rial`,
`parsed_ref`, `received_at`, `created_at`.

### `bank_transactions` (append-only)
`id`, `sms_message_id` FK nullable, `amount_rial`, `reference` UNIQUE, `sender_masked`,
`bank`, `received_at`, `matched_intent_id` FK nullable, `created_at`.

### `shop_cards`
`id`, `label`, `pan_last4`, `holder_fa`, `bank`, `is_active`, timestamps. Full PAN is env-only.

### `payment_proofs`
`id`, `intent_id` FK, `user_id` FK, `telegram_file_id`, `status` ∈ `pending|approved|rejected`,
`reviewer_telegram_id`, `note`, timestamps.

### `card_bindings`
`id`, `user_id` FK, `pan_last4`, `label`, `is_active`, timestamps.

## Operations

### `wallet_transactions` (append-only)
`id`, `user_id` FK, `delta_rial` (signed, non-zero), `balance_after_rial`,
`type` ∈ `topup|order_payment|refund|admin_credit|admin_debit`, `reason`, `ref_type`, `ref_id`,
`actor_telegram_id`, `created_at`.

### `admin_audit_log`
`id`, `actor_telegram_id`, `action`, `target_type`, `target_id`, `payload` JSON, `created_at`.

### `broadcasts` / `broadcast_targets`
`broadcasts`: `id`, `text_fa`, `media_file_id`, `creator_telegram_id`, `status`,
`sent_count`, `failed_count`, timestamps.
`broadcast_targets`: `id`, `broadcast_id` FK, `user_id` FK, `status`, `sent_at`.

### `support_threads` / `support_messages`
Threads: `id`, `user_id` FK, `status`, `assignee_telegram_id`, timestamps.
Messages: `id`, `thread_id` FK, `sender_role` ∈ `user|admin`, `text_fa`, `file_id`, `created_at`.

### `jobs` / `settings`
`jobs`: deferred work (`kind`, `payload` JSON, `run_at`, `status`, `attempts`).
`settings`: runtime key/value (`key` UNIQUE, `value` JSON, `updated_at`).

## Migration notes
- First revision creates the full schema; later changes are additive/backward-compatible.
- Run `alembic upgrade head` on container start (or as a one-shot compose service).
- Partial unique indexes are PostgreSQL-specific — SQLite is intentionally unsupported.
