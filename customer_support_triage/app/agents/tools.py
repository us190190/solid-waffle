"""Tool wrappers for specialists. File: app/agents/tools.py:1"""
from app.core import mock_db


def billing_tools():
    return {
        "lookup_invoice": mock_db.lookup_invoice,
        "check_refund_status": mock_db.check_refund_status,
        "update_payment_method": mock_db.update_payment_method,
    }


def technical_tools():
    return {
        "check_system_status": mock_db.check_system_status,
        "lookup_ticket": mock_db.lookup_ticket,
        "restart_service_mock": mock_db.restart_service_mock,
    }


def sales_tools():
    return {
        "lookup_pricing": mock_db.lookup_pricing,
        "check_inventory": mock_db.check_inventory,
        "create_lead": mock_db.create_lead,
    }
