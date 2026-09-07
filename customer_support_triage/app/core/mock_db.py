"""In-memory mock DB/API for specialist tools. File: app/core/mock_db.py:1"""
from typing import Dict, List

# Billing mock data
INVOICES: Dict[str, Dict] = {
    "INV-001": {"invoice_id": "INV-001", "customer": "Acme Corp", "amount": 199.99, "status": "paid",
                "due_date": "2026-08-01"},
    "INV-002": {"invoice_id": "INV-002", "customer": "Acme Corp", "amount": 349.50, "status": "overdue",
                "due_date": "2026-07-15"},
    "INV-003": {"invoice_id": "INV-003", "customer": "Globex", "amount": 59.00, "status": "refunded",
                "due_date": "2026-06-20"},
}

REFUNDS: Dict[str, Dict] = {
    "INV-003": {"refund_id": "REF-003", "invoice_id": "INV-003", "amount": 59.00, "status": "completed"},
}

PAYMENT_METHODS: Dict[str, str] = {"cust_123": "Visa **** 4242"}

# Technical mock data
SYSTEM_STATUS: Dict[str, str] = {"api": "operational", "dashboard": "degraded", "database": "operational"}
TICKETS: Dict[str, Dict] = {
    "TICK-101": {"ticket_id": "TICK-101", "issue": "Login fails with 500", "status": "open", "priority": "high"},
    "TICK-102": {"ticket_id": "TICK-102", "issue": "Slow query on dashboard", "status": "in_progress",
                 "priority": "medium"},
}

# Sales mock data
PRODUCTS: Dict[str, Dict] = {
    "PROD-A": {"sku": "PROD-A", "name": "Pro Plan", "price": 29.99, "stock": 999, "description": "Pro plan monthly"},
    "PROD-B": {"sku": "PROD-B", "name": "Enterprise Plan", "price": 99.99, "stock": 999,
               "description": "Enterprise with SLA"},
}
LEADS: List[Dict] = []
INVENTORY: Dict[str, int] = {"PROD-A": 999, "PROD-B": 999}


# --- Billing tools ---
def lookup_invoice(invoice_id: str) -> Dict:
    inv = INVOICES.get(invoice_id.upper())
    if inv:
        return {"found": True, "invoice": inv}
    return {"found": False, "message": f"Invoice {invoice_id} not found", "available": list(INVOICES.keys())}


def check_refund_status(invoice_id: str) -> Dict:
    inv = INVOICES.get(invoice_id.upper())
    if not inv:
        return {"found": False, "message": f"Invoice {invoice_id} not found"}
    refund = REFUNDS.get(invoice_id.upper())
    if refund:
        return {"found": True, "refund": refund, "invoice_status": inv["status"]}
    return {"found": False, "invoice_status": inv["status"], "message": "No refund issued for this invoice"}


def update_payment_method(customer_id: str, method: str) -> Dict:
    PAYMENT_METHODS[customer_id] = method
    return {"updated": True, "customer_id": customer_id, "method": method}


# --- Technical tools ---
def check_system_status(service: str = "api") -> Dict:
    status = SYSTEM_STATUS.get(service.lower(), "unknown")
    return {"service": service, "status": status, "all": SYSTEM_STATUS}


def lookup_ticket(ticket_id: str) -> Dict:
    t = TICKETS.get(ticket_id.upper())
    if t:
        return {"found": True, "ticket": t}
    return {"found": False, "message": f"Ticket {ticket_id} not found", "available": list(TICKETS.keys())}


def restart_service_mock(service: str) -> Dict:
    prev = SYSTEM_STATUS.get(service, "unknown")
    SYSTEM_STATUS[service] = "operational"
    return {"service": service, "previous_status": prev, "new_status": "operational",
            "message": f"Service {service} restarted (mock)"}


# --- Sales tools ---
def lookup_pricing(sku: str) -> Dict:
    p = PRODUCTS.get(sku.upper())
    if p:
        return {"found": True, "product": p}
    return {"found": False, "message": f"SKU {sku} not found", "available": list(PRODUCTS.keys())}


def check_inventory(sku: str) -> Dict:
    qty = INVENTORY.get(sku.upper())
    if qty is not None:
        return {"sku": sku.upper(), "quantity": qty, "in_stock": qty > 0}
    return {"sku": sku.upper(), "quantity": 0, "in_stock": False, "message": "SKU not found"}


def create_lead(email: str, interest: str) -> Dict:
    lead = {"email": email, "interest": interest, "lead_id": f"LEAD-{len(LEADS) + 1:03d}"}
    LEADS.append(lead)
    return {"created": True, "lead": lead, "total_leads": len(LEADS)}
