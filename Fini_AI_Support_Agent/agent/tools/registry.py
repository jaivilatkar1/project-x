"""Azure OpenAI tool schemas for the four Paylane mock APIs."""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_customer",
            "description": (
                "Look up a customer by email. Account details are returned only when "
                "card_last4 matches the card on file (identity verification). "
                "Never reveal a full card number or invent an email."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Email address the customer claims is on file.",
                    },
                    "card_last4": {
                        "type": "string",
                        "description": (
                            "Last 4 digits the customer confirms. Required to complete "
                            "verification and receive account details."
                        ),
                    },
                },
                "required": ["email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transaction",
            "description": (
                "Fetch a transaction for a verified customer. Requires prior successful "
                "get_customer verification. customer_id must match the verified session."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "txn_id": {"type": "string"},
                },
                "required": ["customer_id", "txn_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": (
                "Attempt a full refund. The API enforces policy: settled only, amount "
                "equals original and ≤ $75, under 30 days old, customer verified, never "
                "twice. Do not call when policy says no — escalate instead when required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "txn_id": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["txn_id", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Create a human support ticket. Use for: amount > $75, age ≥ 30 days, "
                "frozen card unfreeze requests, suspected unauthorized charges, fraud "
                "(especially > $500 total loss), legal action, account closure, explicit "
                "request for a person, unverified customer auto-refund blocks, and after "
                "3 failed identity checks. customer_id may be null/guest for legal/"
                "closure/person requests before verification."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": ["string", "null"],
                        "description": "Verified customer id, or null/guest when allowed.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Short handoff summary for the human agent.",
                    },
                },
                "required": ["summary"],
            },
        },
    },
]
