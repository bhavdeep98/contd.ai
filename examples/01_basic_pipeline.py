"""
Example 01: Basic Data Pipeline

A simple workflow demonstrating sequential step execution
with automatic checkpointing and recovery.
"""

from contd.sdk import workflow, step


@step()
def fetch_data(source: str) -> dict:
    """Fetch data from a source."""
    print(f"Fetching data from {source}...")
    # Simulate API call
    return {
        "items": [
            {"id": 1, "name": "Item A", "value": 100},
            {"id": 2, "name": "Item B", "value": 200},
            {"id": 3, "name": "Item C", "value": 300},
        ]
    }


@step()
def transform_data(data: dict) -> dict:
    """Transform the fetched data."""
    print("Transforming data...")
    items = data.get("items", [])
    transformed = [
        {**item, "value_doubled": item["value"] * 2}
        for item in items
    ]
    return {"transformed_items": transformed}


@step()
def aggregate_results(data: dict) -> dict:
    """Aggregate the transformed data."""
    print("Aggregating results...")
    items = data.get("transformed_items", [])
    total = sum(item["value_doubled"] for item in items)
    return {
        "total_value": total,
        "item_count": len(items),
        "average": total / len(items) if items else 0
    }


@step()
def save_results(results: dict) -> dict:
    """Save results to storage."""
    print(f"Saving results: {results}")
    # Simulate database save
    return {"status": "saved", "results": results}


@workflow()
def data_pipeline(source: str) -> dict:
    """
    A basic data processing pipeline.
    
    Each step is automatically checkpointed. If the workflow
    crashes and restarts, it will resume from the last
    completed step.
    """
    # Step 1: Fetch
    raw_data = fetch_data(source)
    
    # Step 2: Transform
    transformed = transform_data(raw_data)
    
    # Step 3: Aggregate
    aggregated = aggregate_results(transformed)
    
    # Step 4: Save
    final = save_results(aggregated)
    
    return final


if __name__ == "__main__":
    # Run the workflow
    result = data_pipeline("https://api.example.com/data")
    print(f"\nWorkflow completed: {result}")
