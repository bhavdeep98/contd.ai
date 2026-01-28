# Contd SDK for TypeScript/Node.js

Resumable workflows with exactly-once execution semantics.

## Installation

```bash
npm install @contd.ai/sdk
```

## Quick Start

```typescript
import { ContdClient, workflow, step, WorkflowConfig, StepConfig, RetryPolicy } from '@contd.ai/sdk';

// Remote client usage
const client = new ContdClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.contd.ai'
});

// Start a workflow
const workflowId = await client.startWorkflow({
  workflowName: 'process-order',
  input: { orderId: '12345' }
});

// Check status
const status = await client.getStatus(workflowId);
console.log(status.status); // 'running', 'completed', etc.

// Resume interrupted workflow
await client.resume(workflowId);

// Time travel to savepoint
const newWorkflowId = await client.timeTravel(workflowId, 'savepoint-id');
```

## Defining Workflows

```typescript
import { workflow, step, ExecutionContext } from '@contd.ai/sdk';

// Define a step with retry policy
@step({
  retry: {
    maxAttempts: 3,
    backoffBase: 2,
    backoffMax: 60,
    backoffJitter: 0.5
  },
  timeout: 30000
})
async function chargePayment(orderId: string): Promise<{ paymentId: string }> {
  const result = await paymentGateway.charge(orderId);
  return { paymentId: result.id };
}

// Define a workflow
@workflow({ tags: { team: 'platform' } })
async function processOrder(orderId: string) {
  await validateOrder(orderId);
  await chargePayment(orderId);
  await shipOrder(orderId);
}
```

## Testing

```typescript
import { ContdTestCase, WorkflowTestBuilder } from '@contd.ai/sdk';

// Using test case
const testCase = new ContdTestCase();
testCase.setUp();

await testCase.runWorkflow(processOrder, {
  args: ['order-123'],
  interruptAtStep: 2
});
testCase.assertInterrupted(2);

await testCase.resumeWorkflow();
testCase.assertCompleted();

testCase.tearDown();

// Using fluent builder
await new WorkflowTestBuilder(processOrder)
  .withInput('order-123')
  .interruptAt(2)
  .run()
  .assertInterrupted()
  .resume()
  .assertCompleted();
```

## Error Handling

```typescript
import {
  ContdError,
  WorkflowLocked,
  StepTimeout,
  TooManyAttempts
} from '@contd.ai/sdk';

try {
  await client.startWorkflow({ ... });
} catch (error) {
  if (error instanceof WorkflowLocked) {
    console.log('Workflow is locked by:', error.details.currentOwner);
  } else if (error instanceof StepTimeout) {
    console.log('Step timed out:', error.stepName);
  }
}
```

## Features

- Resumable workflows with exactly-once execution
- Automatic retry with exponential backoff
- Step-level timeouts
- Rich savepoints with epistemic metadata
- Idempotent step execution
- Comprehensive error hierarchy
- Testing utilities with mock engine
