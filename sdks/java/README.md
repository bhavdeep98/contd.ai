# Contd SDK for Java

Resumable workflows with exactly-once execution semantics.

## Installation

### Maven

```xml
<dependency>
    <groupId>ai.contd</groupId>
    <artifactId>contd-sdk</artifactId>
    <version>1.0.0</version>
</dependency>
```

### Gradle

```groovy
implementation 'ai.contd:contd-sdk:1.0.0'
```

## Quick Start

```java
import ai.contd.sdk.ContdClient;
import ai.contd.sdk.types.*;

public class Example {
    public static void main(String[] args) throws Exception {
        // Create client
        ContdClient client = ContdClient.builder()
            .apiKey("your-api-key")
            .baseUrl("https://api.contd.ai")
            .build();

        // Start a workflow
        String workflowId = client.startWorkflow(
            "process-order",
            Map.of("orderId", "12345"),
            null
        );

        // Check status
        WorkflowStatusResponse status = client.getStatus(workflowId);
        System.out.println(status.getStatus());

        // Resume interrupted workflow
        client.resume(workflowId);

        // Time travel to savepoint
        String newWorkflowId = client.timeTravel(workflowId, "savepoint-id");
    }
}
```

## Defining Workflows

```java
import ai.contd.sdk.*;
import ai.contd.sdk.types.*;

public class OrderWorkflow {
    private final WorkflowRunner runner;

    public OrderWorkflow(Engine engine) {
        this.runner = new WorkflowRunner(engine, WorkflowConfig.builder()
            .tag("team", "platform")
            .build());
    }

    public Object processOrder(Object input) {
        return runner.run("process-order", this::executeWorkflow, input);
    }

    private Object executeWorkflow(Object input) {
        Map<String, Object> data = (Map<String, Object>) input;
        String orderId = (String) data.get("orderId");

        // Create step runner with retry policy
        WorkflowRunner.StepRunner stepRunner = runner.step(StepConfig.builder()
            .checkpoint(true)
            .retry(RetryPolicy.builder()
                .maxAttempts(3)
                .backoffBase(2.0)
                .backoffMax(60.0)
                .backoffJitter(0.5)
                .build())
            .build());

        try {
            // Execute steps
            stepRunner.run("validate_order", () -> validateOrder(orderId));
            stepRunner.run("charge_payment", () -> chargePayment(orderId));
            stepRunner.run("ship_order", () -> shipOrder(orderId));

            return Map.of("status", "completed");
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
```

## Testing

```java
import ai.contd.sdk.testing.*;
import org.junit.jupiter.api.*;

class OrderWorkflowTest {
    private ContdTestCase testCase;

    @BeforeEach
    void setUp() {
        testCase = new ContdTestCase();
        testCase.setUp();
    }

    @AfterEach
    void tearDown() {
        testCase.tearDown();
    }

    @Test
    void testProcessOrderWithInterruption() {
        // Run with interruption at step 2
        testCase.runWorkflow("process-order", this::processOrder,
            new ContdTestCase.RunWorkflowOptions()
                .input(Map.of("orderId", "123"))
                .interruptAtStep(2));

        testCase.assertInterrupted(2);

        // Resume
        testCase.resumeWorkflow("process-order", this::processOrder, null);
        testCase.assertCompleted();
    }

    @Test
    void testProcessOrderWithFailure() {
        testCase.runWorkflow("process-order", this::processOrder,
            new ContdTestCase.RunWorkflowOptions()
                .input(Map.of("orderId", "123"))
                .failAtStep(1)
                .failWith(new RuntimeException("Payment failed")));

        testCase.assertFailed("Payment failed");
    }
}
```

## Error Handling

```java
import ai.contd.sdk.errors.*;

try {
    client.startWorkflow("process-order", input, null);
} catch (WorkflowLockedException e) {
    System.out.println("Workflow locked by: " + e.getOwnerId());
} catch (WorkflowNotFoundException e) {
    System.out.println("Workflow not found: " + e.getWorkflowId());
} catch (StepTimeoutException e) {
    System.out.println("Step timed out: " + e.getStepName());
} catch (ContdException e) {
    System.out.println("Error: " + e.getMessage());
}
```

## Features

- Resumable workflows with exactly-once execution
- Automatic retry with exponential backoff
- Step-level timeouts
- Rich savepoints with epistemic metadata
- Idempotent step execution
- Comprehensive exception hierarchy
- Testing utilities with mock engine
- Builder patterns for configuration
- Java 17+ support
