"""
Example 06: Data ETL Pipeline

Extract-Transform-Load workflow for data processing.
Demonstrates batch processing with checkpoints.
"""

from contd.sdk import workflow, step, StepConfig
from datetime import datetime


@step()
def extract_from_source(source_config: dict) -> dict:
    """Extract data from source system."""
    print(f"Extracting from {source_config['type']}...")
    
    # Simulate data extraction
    records = [
        {"id": 1, "name": "Alice", "email": "alice@example.com", "created": "2025-01-01"},
        {"id": 2, "name": "Bob", "email": "bob@example.com", "created": "2025-01-02"},
        {"id": 3, "name": "Charlie", "email": "charlie@example.com", "created": "2025-01-03"},
        {"id": 4, "name": "Diana", "email": "diana@example.com", "created": "2025-01-04"},
        {"id": 5, "name": "Eve", "email": "eve@example.com", "created": "2025-01-05"},
    ]
    
    return {
        "records": records,
        "source": source_config["type"],
        "extracted_at": datetime.now().isoformat(),
        "count": len(records)
    }


@step()
def validate_records(data: dict) -> dict:
    """Validate extracted records."""
    print(f"Validating {data['count']} records...")
    
    valid = []
    invalid = []
    
    for record in data["records"]:
        # Validation rules
        if not record.get("email") or "@" not in record["email"]:
            invalid.append({"record": record, "reason": "Invalid email"})
        elif not record.get("name"):
            invalid.append({"record": record, "reason": "Missing name"})
        else:
            valid.append(record)
    
    return {
        "valid_records": valid,
        "invalid_records": invalid,
        "valid_count": len(valid),
        "invalid_count": len(invalid)
    }


@step()
def transform_records(data: dict) -> dict:
    """Transform records to target schema."""
    print(f"Transforming {data['valid_count']} records...")
    
    transformed = []
    for record in data["valid_records"]:
        transformed.append({
            "user_id": f"USR-{record['id']:05d}",
            "full_name": record["name"].upper(),
            "email_address": record["email"].lower(),
            "registration_date": record["created"],
            "processed_at": datetime.now().isoformat()
        })
    
    return {
        "transformed_records": transformed,
        "count": len(transformed)
    }


@step()
def enrich_records(data: dict) -> dict:
    """Enrich records with additional data."""
    print(f"Enriching {data['count']} records...")
    
    enriched = []
    for record in data["transformed_records"]:
        # Simulate enrichment (e.g., from external API)
        enriched.append({
            **record,
            "email_domain": record["email_address"].split("@")[1],
            "account_status": "active",
            "tier": "standard"
        })
    
    return {
        "enriched_records": enriched,
        "count": len(enriched)
    }


@step()
def load_to_destination(data: dict, destination_config: dict) -> dict:
    """Load records to destination system."""
    print(f"Loading {data['count']} records to {destination_config['type']}...")
    
    # Simulate database insert
    loaded_ids = [r["user_id"] for r in data["enriched_records"]]
    
    return {
        "loaded_count": len(loaded_ids),
        "loaded_ids": loaded_ids,
        "destination": destination_config["type"],
        "loaded_at": datetime.now().isoformat()
    }


@step()
def generate_report(extract_result: dict, validate_result: dict, load_result: dict) -> dict:
    """Generate ETL summary report."""
    print("Generating ETL report...")
    
    return {
        "report": {
            "source": extract_result["source"],
            "destination": load_result["destination"],
            "extracted": extract_result["count"],
            "valid": validate_result["valid_count"],
            "invalid": validate_result["invalid_count"],
            "loaded": load_result["loaded_count"],
            "started_at": extract_result["extracted_at"],
            "completed_at": load_result["loaded_at"],
            "status": "success"
        }
    }


@workflow()
def etl_pipeline(source_config: dict, destination_config: dict) -> dict:
    """
    Complete ETL pipeline:
    1. Extract from source
    2. Validate records
    3. Transform to target schema
    4. Enrich with additional data
    5. Load to destination
    6. Generate report
    
    Each step is checkpointed. If the pipeline fails,
    it can resume from the last successful step.
    """
    # Extract
    extracted = extract_from_source(source_config)
    
    # Validate
    validated = validate_records(extracted)
    
    # Transform
    transformed = transform_records(validated)
    
    # Enrich
    enriched = enrich_records(transformed)
    
    # Load
    loaded = load_to_destination(enriched, destination_config)
    
    # Report
    report = generate_report(extracted, validated, loaded)
    
    return report


if __name__ == "__main__":
    source = {"type": "postgresql", "table": "users"}
    destination = {"type": "snowflake", "table": "dim_users"}
    
    result = etl_pipeline(source, destination)
    print(f"\nETL Report:")
    for key, value in result["report"].items():
        print(f"  {key}: {value}")
