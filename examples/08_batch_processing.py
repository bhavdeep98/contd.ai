"""
Example 08: Batch Processing

Process large datasets in batches with progress tracking.
Demonstrates handling large workloads with checkpoints.
"""

from contd.sdk import workflow, step, StepConfig, ExecutionContext
from typing import List
import time


@step()
def fetch_batch_ids(source: str, batch_size: int) -> dict:
    """Fetch IDs of items to process."""
    print(f"Fetching batch IDs from {source}...")
    
    # Simulate fetching IDs (in production: query database)
    all_ids = list(range(1, 101))  # 100 items
    
    # Split into batches
    batches = [
        all_ids[i:i + batch_size]
        for i in range(0, len(all_ids), batch_size)
    ]
    
    return {
        "total_items": len(all_ids),
        "batch_size": batch_size,
        "num_batches": len(batches),
        "batches": batches
    }


@step(StepConfig(savepoint=True))
def process_batch(batch_num: int, item_ids: List[int], total_batches: int) -> dict:
    """
    Process a single batch of items.
    
    Creates a savepoint after each batch for progress tracking.
    """
    ctx = ExecutionContext.current()
    
    print(f"Processing batch {batch_num + 1}/{total_batches} ({len(item_ids)} items)...")
    
    results = []
    errors = []
    
    for item_id in item_ids:
        try:
            # Simulate processing
            time.sleep(0.01)  # 10ms per item
            results.append({
                "id": item_id,
                "status": "processed",
                "result": f"Result for item {item_id}"
            })
        except Exception as e:
            errors.append({"id": item_id, "error": str(e)})
    
    # Create savepoint with progress
    progress = (batch_num + 1) / total_batches * 100
    ctx.create_savepoint({
        "goal_summary": f"Batch processing: {progress:.1f}% complete",
        "hypotheses": [],
        "questions": [],
        "decisions": [f"Completed batch {batch_num + 1}"],
        "next_step": f"Process batch {batch_num + 2}" if batch_num + 1 < total_batches else "Finalize"
    })
    
    return {
        "batch_num": batch_num,
        "processed": len(results),
        "errors": len(errors),
        "results": results,
        "error_details": errors
    }


@step()
def aggregate_results(batch_results: List[dict]) -> dict:
    """Aggregate results from all batches."""
    print("Aggregating batch results...")
    
    total_processed = sum(b["processed"] for b in batch_results)
    total_errors = sum(b["errors"] for b in batch_results)
    
    return {
        "total_processed": total_processed,
        "total_errors": total_errors,
        "success_rate": total_processed / (total_processed + total_errors) if total_processed + total_errors > 0 else 0,
        "batches_completed": len(batch_results)
    }


@step()
def save_results(aggregated: dict, destination: str) -> dict:
    """Save aggregated results."""
    print(f"Saving results to {destination}...")
    
    return {
        "saved": True,
        "destination": destination,
        "summary": aggregated
    }


@step()
def send_completion_notification(results: dict) -> dict:
    """Send notification when processing completes."""
    print("Sending completion notification...")
    
    return {
        "notification_sent": True,
        "message": f"Batch processing complete: {results['summary']['total_processed']} items processed"
    }


@workflow()
def batch_processing_workflow(source: str, destination: str, batch_size: int = 10) -> dict:
    """
    Process large dataset in batches:
    1. Fetch all item IDs
    2. Process each batch (with savepoints)
    3. Aggregate results
    4. Save to destination
    5. Send notification
    
    If the workflow crashes, it resumes from the last
    completed batch thanks to savepoints.
    """
    # Fetch batch IDs
    batch_info = fetch_batch_ids(source, batch_size)
    
    # Process each batch
    batch_results = []
    for i, batch_ids in enumerate(batch_info["batches"]):
        result = process_batch(i, batch_ids, batch_info["num_batches"])
        batch_results.append(result)
    
    # Aggregate
    aggregated = aggregate_results(batch_results)
    
    # Save
    saved = save_results(aggregated, destination)
    
    # Notify
    notification = send_completion_notification(saved)
    
    return {
        "status": "completed",
        "total_items": batch_info["total_items"],
        "processed": aggregated["total_processed"],
        "errors": aggregated["total_errors"],
        "success_rate": f"{aggregated['success_rate'] * 100:.1f}%",
        "notification": notification["message"]
    }


if __name__ == "__main__":
    result = batch_processing_workflow(
        source="postgresql://db/items",
        destination="s3://bucket/results",
        batch_size=20
    )
    
    print(f"\nBatch Processing Result:")
    print(f"  Status: {result['status']}")
    print(f"  Total Items: {result['total_items']}")
    print(f"  Processed: {result['processed']}")
    print(f"  Errors: {result['errors']}")
    print(f"  Success Rate: {result['success_rate']}")
