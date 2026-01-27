"""
Example 05: Order Processing (Saga Pattern)

E-commerce order workflow with compensation for failures.
Demonstrates the saga pattern for distributed transactions.
"""

from contd.sdk import workflow, step, StepConfig, RetryPolicy


class OrderError(Exception):
    """Order processing error."""
    pass


@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def validate_order(order: dict) -> dict:
    """Validate order details."""
    print(f"Validating order {order['id']}...")
    
    if not order.get("items"):
        raise OrderError("Order has no items")
    
    if order.get("total", 0) <= 0:
        raise OrderError("Invalid order total")
    
    return {"validated": True, "order_id": order["id"]}


@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def reserve_inventory(order: dict) -> dict:
    """Reserve inventory for order items."""
    print(f"Reserving inventory for order {order['id']}...")
    
    reservations = []
    for item in order["items"]:
        # Simulate inventory check
        reservation_id = f"res-{item['sku']}-{order['id']}"
        reservations.append({
            "sku": item["sku"],
            "quantity": item["quantity"],
            "reservation_id": reservation_id
        })
    
    return {"reservations": reservations}


@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def charge_payment(order: dict) -> dict:
    """Process payment for the order."""
    print(f"Charging payment for order {order['id']}...")
    
    # Simulate payment processing
    payment_id = f"pay-{order['id']}"
    
    return {
        "payment_id": payment_id,
        "amount": order["total"],
        "status": "charged"
    }


@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def create_shipment(order: dict, reservations: list) -> dict:
    """Create shipment for the order."""
    print(f"Creating shipment for order {order['id']}...")
    
    shipment_id = f"ship-{order['id']}"
    
    return {
        "shipment_id": shipment_id,
        "tracking_number": f"TRK{order['id']}",
        "status": "created"
    }


@step()
def send_confirmation(order: dict, payment: dict, shipment: dict) -> dict:
    """Send order confirmation to customer."""
    print(f"Sending confirmation for order {order['id']}...")
    
    return {
        "email_sent": True,
        "order_id": order["id"],
        "tracking": shipment["tracking_number"]
    }


# Compensation steps (for rollback)
@step()
def release_inventory(reservations: list) -> dict:
    """Release reserved inventory (compensation)."""
    print(f"Releasing {len(reservations)} inventory reservations...")
    return {"released": [r["reservation_id"] for r in reservations]}


@step()
def refund_payment(payment: dict) -> dict:
    """Refund payment (compensation)."""
    print(f"Refunding payment {payment['payment_id']}...")
    return {"refund_id": f"ref-{payment['payment_id']}", "status": "refunded"}


@step()
def cancel_shipment(shipment: dict) -> dict:
    """Cancel shipment (compensation)."""
    print(f"Canceling shipment {shipment['shipment_id']}...")
    return {"canceled": True, "shipment_id": shipment["shipment_id"]}


@workflow()
def process_order(order: dict) -> dict:
    """
    Process an e-commerce order with saga pattern.
    
    If any step fails, compensating transactions are
    executed to maintain consistency.
    
    Steps:
    1. Validate order
    2. Reserve inventory
    3. Charge payment
    4. Create shipment
    5. Send confirmation
    
    Compensations (on failure):
    - Cancel shipment
    - Refund payment
    - Release inventory
    """
    completed = {}
    
    try:
        # Step 1: Validate
        validate_order(order)
        
        # Step 2: Reserve inventory
        inventory = reserve_inventory(order)
        completed["inventory"] = inventory
        
        # Step 3: Charge payment
        payment = charge_payment(order)
        completed["payment"] = payment
        
        # Step 4: Create shipment
        shipment = create_shipment(order, inventory["reservations"])
        completed["shipment"] = shipment
        
        # Step 5: Send confirmation
        confirmation = send_confirmation(order, payment, shipment)
        
        return {
            "status": "completed",
            "order_id": order["id"],
            "payment": payment,
            "shipment": shipment,
            "confirmation": confirmation
        }
        
    except Exception as e:
        print(f"Order failed: {e}. Running compensations...")
        
        # Compensate in reverse order
        if "shipment" in completed:
            cancel_shipment(completed["shipment"])
        
        if "payment" in completed:
            refund_payment(completed["payment"])
        
        if "inventory" in completed:
            release_inventory(completed["inventory"]["reservations"])
        
        return {
            "status": "failed",
            "order_id": order["id"],
            "error": str(e),
            "compensated": list(completed.keys())
        }


if __name__ == "__main__":
    order = {
        "id": "ORD-12345",
        "customer_id": "CUST-001",
        "items": [
            {"sku": "WIDGET-A", "quantity": 2, "price": 29.99},
            {"sku": "GADGET-B", "quantity": 1, "price": 49.99},
        ],
        "total": 109.97,
        "shipping_address": {
            "street": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94102"
        }
    }
    
    result = process_order(order)
    print(f"\nOrder result: {result}")
