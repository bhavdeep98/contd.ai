"""
Example 12: Customer Support Automation

Automated customer support ticket handling workflow.
Demonstrates classification, routing, and response generation.
"""

from contd.sdk import workflow, step, StepConfig, ExecutionContext
from typing import Dict, List
import time


@step()
def receive_ticket(ticket_data: dict) -> dict:
    """Receive and normalize incoming support ticket."""
    print(f"Receiving ticket from {ticket_data.get('channel', 'unknown')}...")
    
    ticket_id = f"TKT-{int(time.time())}"
    
    return {
        "ticket_id": ticket_id,
        "customer_id": ticket_data.get("customer_id"),
        "customer_email": ticket_data.get("email"),
        "subject": ticket_data.get("subject", "No subject"),
        "body": ticket_data.get("body", ""),
        "channel": ticket_data.get("channel", "email"),
        "priority": "unset",
        "category": "unclassified",
        "received_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@step()
def classify_ticket(ticket: dict) -> dict:
    """Classify ticket category and priority using AI."""
    print(f"Classifying ticket {ticket['ticket_id']}...")
    
    body_lower = ticket["body"].lower()
    
    # Simple rule-based classification (in production: use LLM)
    if "urgent" in body_lower or "emergency" in body_lower:
        priority = "high"
    elif "asap" in body_lower or "important" in body_lower:
        priority = "medium"
    else:
        priority = "low"
    
    if "billing" in body_lower or "payment" in body_lower or "invoice" in body_lower:
        category = "billing"
    elif "bug" in body_lower or "error" in body_lower or "broken" in body_lower:
        category = "technical"
    elif "cancel" in body_lower or "refund" in body_lower:
        category = "cancellation"
    elif "how" in body_lower or "help" in body_lower:
        category = "general_inquiry"
    else:
        category = "other"
    
    return {
        **ticket,
        "priority": priority,
        "category": category,
        "classification_confidence": 0.85
    }


@step()
def fetch_customer_context(customer_id: str) -> dict:
    """Fetch customer history and context."""
    print(f"Fetching context for customer {customer_id}...")
    
    # Simulate customer lookup
    return {
        "customer_id": customer_id,
        "name": "John Doe",
        "plan": "premium",
        "tenure_months": 24,
        "previous_tickets": 3,
        "satisfaction_score": 4.2,
        "recent_activity": [
            {"type": "login", "date": "2025-01-26"},
            {"type": "purchase", "date": "2025-01-20"}
        ]
    }


@step()
def search_knowledge_base(category: str, query: str) -> dict:
    """Search knowledge base for relevant articles."""
    print(f"Searching knowledge base for {category}...")
    
    # Simulate KB search
    articles = {
        "billing": [
            {"id": "KB-001", "title": "How to update payment method", "relevance": 0.9},
            {"id": "KB-002", "title": "Understanding your invoice", "relevance": 0.8}
        ],
        "technical": [
            {"id": "KB-010", "title": "Troubleshooting common errors", "relevance": 0.85},
            {"id": "KB-011", "title": "System requirements", "relevance": 0.7}
        ],
        "cancellation": [
            {"id": "KB-020", "title": "Cancellation policy", "relevance": 0.95},
            {"id": "KB-021", "title": "Refund process", "relevance": 0.9}
        ],
        "general_inquiry": [
            {"id": "KB-030", "title": "Getting started guide", "relevance": 0.8},
            {"id": "KB-031", "title": "FAQ", "relevance": 0.75}
        ]
    }
    
    return {
        "articles": articles.get(category, []),
        "category": category
    }


@step(StepConfig(savepoint=True))
def generate_response(
    ticket: dict,
    customer: dict,
    kb_results: dict
) -> dict:
    """Generate response using AI with context."""
    ctx = ExecutionContext.current()
    
    print(f"Generating response for ticket {ticket['ticket_id']}...")
    
    # Build context for response generation
    context = {
        "ticket": ticket,
        "customer_name": customer["name"],
        "customer_plan": customer["plan"],
        "relevant_articles": kb_results["articles"]
    }
    
    # Generate response (in production: use LLM)
    if ticket["category"] == "billing":
        response = f"""Hi {customer['name']},

Thank you for reaching out about your billing inquiry.

I've reviewed your account and can help you with this. Based on your question, you might find these resources helpful:
{chr(10).join(f"- {a['title']}" for a in kb_results['articles'][:2])}

If you need further assistance, please let me know.

Best regards,
Support Team"""
    else:
        response = f"""Hi {customer['name']},

Thank you for contacting support. I understand you need help with {ticket['category']}.

I've found some resources that might help:
{chr(10).join(f"- {a['title']}" for a in kb_results['articles'][:2])}

Please let me know if you have any other questions.

Best regards,
Support Team"""
    
    # Create savepoint with reasoning
    ctx.create_savepoint({
        "goal_summary": f"Respond to {ticket['category']} ticket",
        "hypotheses": [
            "Customer needs help with " + ticket["category"],
            "KB articles will be helpful"
        ],
        "questions": ["Is this the right response?", "Should we escalate?"],
        "decisions": [
            f"Using {len(kb_results['articles'])} KB articles",
            f"Response tone: professional"
        ],
        "next_step": "determine_routing"
    })
    
    return {
        "response": response,
        "response_type": "auto_generated",
        "confidence": 0.8,
        "kb_articles_used": [a["id"] for a in kb_results["articles"][:2]]
    }


@step()
def determine_routing(ticket: dict, response: dict) -> dict:
    """Determine if ticket needs human review."""
    print("Determining routing...")
    
    needs_human = (
        ticket["priority"] == "high" or
        response["confidence"] < 0.7 or
        ticket["category"] == "cancellation"
    )
    
    if needs_human:
        # Route to appropriate team
        team_mapping = {
            "billing": "billing_team",
            "technical": "tech_support",
            "cancellation": "retention_team",
            "other": "general_support"
        }
        assigned_team = team_mapping.get(ticket["category"], "general_support")
    else:
        assigned_team = "auto_response"
    
    return {
        "needs_human_review": needs_human,
        "assigned_team": assigned_team,
        "auto_send": not needs_human
    }


@step()
def send_response(ticket: dict, response: dict, routing: dict) -> dict:
    """Send response to customer or queue for review."""
    print(f"Processing response for ticket {ticket['ticket_id']}...")
    
    if routing["auto_send"]:
        # Auto-send response
        return {
            "sent": True,
            "method": "auto",
            "sent_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    else:
        # Queue for human review
        return {
            "sent": False,
            "method": "queued",
            "queued_for": routing["assigned_team"],
            "queued_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }


@step()
def update_ticket_status(ticket: dict, routing: dict, send_result: dict) -> dict:
    """Update ticket status in system."""
    print(f"Updating ticket {ticket['ticket_id']} status...")
    
    if send_result["sent"]:
        status = "responded"
    elif routing["needs_human_review"]:
        status = "pending_review"
    else:
        status = "in_progress"
    
    return {
        "ticket_id": ticket["ticket_id"],
        "status": status,
        "assigned_team": routing["assigned_team"],
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@workflow()
def customer_support_workflow(ticket_data: dict) -> dict:
    """
    Automated customer support workflow:
    1. Receive and normalize ticket
    2. Classify category and priority
    3. Fetch customer context
    4. Search knowledge base
    5. Generate AI response
    6. Determine routing (auto vs human)
    7. Send or queue response
    8. Update ticket status
    
    High-priority and sensitive tickets are routed
    to human agents for review.
    """
    # Receive
    ticket = receive_ticket(ticket_data)
    
    # Classify
    classified = classify_ticket(ticket)
    
    # Get context
    customer = fetch_customer_context(classified["customer_id"])
    
    # Search KB
    kb_results = search_knowledge_base(classified["category"], classified["body"])
    
    # Generate response
    response = generate_response(classified, customer, kb_results)
    
    # Route
    routing = determine_routing(classified, response)
    
    # Send/queue
    send_result = send_response(classified, response, routing)
    
    # Update status
    final_status = update_ticket_status(classified, routing, send_result)
    
    return {
        "ticket_id": classified["ticket_id"],
        "category": classified["category"],
        "priority": classified["priority"],
        "status": final_status["status"],
        "assigned_team": routing["assigned_team"],
        "auto_responded": send_result["sent"],
        "response_preview": response["response"][:100] + "..."
    }


if __name__ == "__main__":
    # Example ticket
    ticket_data = {
        "customer_id": "CUST-12345",
        "email": "john@example.com",
        "subject": "Question about my invoice",
        "body": "Hi, I received my invoice but I don't understand the charges. Can you help explain?",
        "channel": "email"
    }
    
    result = customer_support_workflow(ticket_data)
    
    print(f"\nSupport Ticket Processed!")
    print(f"Ticket ID: {result['ticket_id']}")
    print(f"Category: {result['category']}")
    print(f"Priority: {result['priority']}")
    print(f"Status: {result['status']}")
    print(f"Assigned To: {result['assigned_team']}")
    print(f"Auto-Responded: {result['auto_responded']}")
