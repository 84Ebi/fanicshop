# TASK-003 — Order models

**Status:** done

## Description
Orders with immutable line items and timestamped status history.

## Goal
Represent the full order lifecycle and amounts without mutable price data.

## Acceptance criteria
- [x] `Order` public_code, status, payment_state, all amounts in Rial, address JSON snapshot.
- [x] CHECK `total_rial = subtotal + delivery - discount`; valid status/payment_state.
- [x] `OrderItem` snapshots title/unit price; CHECK line math.
- [x] `OrderStatusHistory` from/to/source/actor/note with created_at.

## Files affected
`app/db/models/orders.py`.

## Test steps
Insert order + item + history; assert line/total math constraints and status values.

## Final status
done.
