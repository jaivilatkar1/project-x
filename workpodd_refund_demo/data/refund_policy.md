# ShopFlow E-Commerce Refund Policy (STRICT)

**Effective:** January 1, 2026  
**Policy ID:** RF-2026-001

## 1. Eligibility windows (from delivery date)

| Customer tier | Return/refund window |
|---------------|---------------------|
| Standard      | 30 calendar days    |
| Premium       | 45 calendar days    |
| VIP           | 60 calendar days    |

## 2. Refund limits per customer (rolling 12 months)

| Tier     | Max approved refunds |
|----------|---------------------|
| Standard | 2                   |
| Premium  | 4                   |
| VIP      | 6                   |

## 3. Non-refundable categories (NO EXCEPTIONS)

- Digital downloads after the download link was accessed
- Items marked **Final Sale** or **Clearance**
- Gift cards and store credit
- Personalized / custom-made products
- Perishable goods after delivery

## 4. Order status requirements

- Refund may only be processed if order status is **delivered**
- Orders in **shipped**, **processing**, or **cancelled** are NOT eligible
- Partial refunds require item-level return confirmation

## 5. Amount thresholds

- Auto-approve refunds up to **$150.00** when all policy rules pass
- Refunds **$150.01 – $500.00** require `manager_approval` flag (agent must escalate)
- Refunds **over $500.00** are **DENIED** — escalate to human supervisor only

## 6. Fraud & abuse

- Deny if `account_status` is **suspended** or **flagged**
- Deny if customer requests refund on same order twice
- Deny if reason is vague and order is outside window (do not guess)

## 7. Required verification steps (agent MUST call tools)

1. Look up customer profile in CRM
2. Verify order exists and belongs to customer
3. Run policy check tool before approving or denying
4. Only call `process_refund` after policy check returns `approved: true`

## 8. Agent communication rules

- Be polite and empathetic
- When denying, cite the specific policy section
- Never promise a refund before policy validation completes
- Offer alternatives: store credit (if VIP), exchange, or escalation
