# Contd SDK for Go

Resumable workflows with exactly-once execution semantics.

## Installation

```bash
go get github.com/contd/sdk-go
```

## Quick Start

```go
package main

import (
    "context"
    "fmt"
    contd "github.com/contd/sdk-go"
)

func main() {
    // Create client
    client := contd.NewClient(contd.ClientConfig{
        APIKey:  "your-api-key",
        BaseURL: "https://api.contd.ai",
    })

    // Start a workflow
    workflowID, err := client.StartWorkflow(context.Background(), contd.StartWorkflowInput{
        WorkflowName: "process-order",
        Input:        map[string]interface{}{"orderId": "12345"},
    })
    if err != nil {
        panic(err)
    }

    // Check status
    status, err := client.GetStatus(context.Background(), workflowID)
    fmt.Println(status.Status)

    // Resume interrupted workflow
    client.Resume(context.Background(), workflowID)
}
```

## Defining Workflows

```go
package main

import (
    "context"
    contd "github.com/contd/sdk-go"
)

func processOrder(ctx context.Context, input interface{}) (interface{}, error) {
    data := input.(map[string]interface{})
    orderId := data["orderId"].(string)

    // Create step runner with retry policy
    stepRunner := contd.NewStepRunner(contd.StepConfig{
        Checkpoint: true,
        Retry: &contd.RetryPolicy{
            MaxAttempts:   3,
            BackoffBase:   2.0,
            BackoffMax:    60.0,
            BackoffJitter: 0.5,
        },
    })

    // Execute steps
    _, err := stepRunner.Run(ctx, "validate_order", func(ctx context.Context, _ interface{}) (interface{}, error) {
        return validateOrder(orderId)
    }, nil)
    if err != nil {
        return nil, err
    }

    _, err = stepRunner.Run(ctx, "charge_payment", func(ctx context.Context, _ interface{}) (interface{}, error) {
        return chargePayment(orderId)
    }, nil)
    if err != nil {
        return nil, err
    }

    return map[string]interface{}{"status": "completed"}, nil
}

func main() {
    // Register workflow
    contd.RegisterWorkflow("process-order", processOrder)

    // Create engine and runner
    engine := contd.NewMockEngine() // Use real engine in production
    runner := contd.NewWorkflowRunner(engine, contd.WorkflowConfig{
        Tags: map[string]string{"team": "platform"},
    })

    // Run workflow
    result, err := runner.Run(context.Background(), "process-order", processOrder, map[string]interface{}{
        "orderId": "12345",
    })
}
```

## Testing

```go
package main

import (
    "context"
    "testing"
    contd "github.com/contd/sdk-go"
)

func TestProcessOrder(t *testing.T) {
    tc := contd.NewTestCase()
    tc.SetUp()
    defer tc.TearDown()

    // Run with interruption
    step := 2
    _, err := tc.RunWorkflow(context.Background(), "process-order", processOrder, contd.RunWorkflowOptions{
        Input:           map[string]interface{}{"orderId": "123"},
        InterruptAtStep: &step,
    })

    if err := tc.AssertInterrupted(&step); err != nil {
        t.Error(err)
    }

    // Resume
    _, err = tc.ResumeWorkflow(context.Background(), "process-order", processOrder, nil)

    if err := tc.AssertCompleted(); err != nil {
        t.Error(err)
    }
}
```

## Error Handling

```go
import contd "github.com/contd/sdk-go"

result, err := client.StartWorkflow(ctx, input)
if err != nil {
    switch e := err.(type) {
    case *contd.WorkflowLocked:
        fmt.Println("Workflow locked by:", e.OwnerID)
    case *contd.WorkflowNotFound:
        fmt.Println("Workflow not found:", e.WorkflowID)
    case *contd.StepTimeout:
        fmt.Println("Step timed out:", e.StepName)
    default:
        fmt.Println("Error:", err)
    }
}
```

## Features

- Resumable workflows with exactly-once execution
- Automatic retry with exponential backoff
- Step-level timeouts
- Rich savepoints with epistemic metadata
- Idempotent step execution
- Comprehensive error types
- Testing utilities with mock engine
- Context-based execution
