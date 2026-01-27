/**
 * Workflow and Step Decorators
 * TypeScript decorators for defining resumable workflows
 */

import { WorkflowConfig, StepConfig, RetryPolicy, WorkflowState } from './types';
import { ExecutionContext, ExecutionEngine, Lease } from './context';
import {
  WorkflowLocked,
  StepTimeout,
  TooManyAttempts,
  StepExecutionFailed,
} from './errors';
import { WorkflowRegistry } from './registry';

// ============================================================================
// Retry Policy Helpers
// ============================================================================

function shouldRetry(
  policy: RetryPolicy,
  attempt: number,
  error: Error
): boolean {
  if (attempt >= policy.maxAttempts) return false;
  if (policy.retryableErrors && policy.retryableErrors.length > 0) {
    return policy.retryableErrors.includes(error.name);
  }
  return true;
}

function calculateBackoff(policy: RetryPolicy, attempt: number): number {
  const delay = Math.min(
    Math.pow(policy.backoffBase, attempt),
    policy.backoffMax
  );
  const jitterRange = delay * policy.backoffJitter;
  return delay - jitterRange / 2 + Math.random() * jitterRange;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ============================================================================
// Workflow Decorator
// ============================================================================

export interface WorkflowOptions extends WorkflowConfig {
  engine?: ExecutionEngine;
}

/**
 * Mark a function as a resumable workflow
 * 
 * @example
 * ```typescript
 * @workflow({ tags: { team: 'platform' } })
 * async function processOrder(orderId: string) {
 *   await validateOrder(orderId);
 *   await chargePayment(orderId);
 *   await shipOrder(orderId);
 * }
 * ```
 */
export function workflow(options: WorkflowOptions = {}) {
  return function <T extends (...args: unknown[]) => Promise<unknown>>(
    target: T,
    context: ClassMethodDecoratorContext | undefined
  ): T {
    const workflowName =
      typeof context?.name === 'string' ? context.name : target.name;

    const wrapper = async function (
      this: unknown,
      ...args: Parameters<T>
    ): Promise<ReturnType<T>> {
      const startTime = Date.now();

      // Get or create context
      const ctx = ExecutionContext.getOrCreate(
        options.workflowId,
        workflowName,
        options.orgId,
        options.tags
      );

      const engine = options.engine;
      if (!engine) {
        throw new Error('ExecutionEngine not provided in workflow options');
      }

      ctx.setEngine(engine);

      // Acquire lease
      const leaseStart = Date.now();
      const lease = await engine.leaseManager.acquire(
        ctx.workflowId,
        ctx.executorId
      );

      if (!lease) {
        throw new WorkflowLocked(ctx.workflowId);
      }

      ctx.setLease(lease);

      try {
        // Start heartbeat
        ctx.startHeartbeat(lease, engine);

        // Check if resuming
        if (ctx.isResuming()) {
          const state = await engine.restore(ctx.workflowId);
          ctx.setState(state);
          console.log(
            `Resumed workflow ${ctx.workflowId} from step ${state.stepNumber}`
          );
        }

        // Execute workflow within context
        const result = await ctx.run(() => target.apply(this, args));

        // Mark complete
        await engine.completeWorkflow(ctx.workflowId);

        return result as ReturnType<T>;
      } finally {
        ctx.stopHeartbeat();
        await engine.leaseManager.release(lease);
      }
    } as T;

    // Attach metadata
    Object.defineProperty(wrapper, '__contd_workflow__', { value: true });
    Object.defineProperty(wrapper, '__contd_config__', { value: options });
    Object.defineProperty(wrapper, 'name', { value: workflowName });

    // Register workflow
    WorkflowRegistry.register(workflowName, wrapper);

    return wrapper;
  };
}

// ============================================================================
// Step Decorator
// ============================================================================

export interface StepOptions extends StepConfig {}

/**
 * Mark a function as a workflow step
 * 
 * @example
 * ```typescript
 * @step({
 *   retry: { maxAttempts: 3, backoffBase: 2 },
 *   timeout: 30000
 * })
 * async function chargePayment(orderId: string): Promise<{ paymentId: string }> {
 *   const result = await paymentGateway.charge(orderId);
 *   return { paymentId: result.id };
 * }
 * ```
 */
export function step(options: StepOptions = {}) {
  const config: Required<StepConfig> = {
    checkpoint: options.checkpoint ?? true,
    idempotencyKey: options.idempotencyKey ?? undefined,
    retry: options.retry ?? undefined,
    timeout: options.timeout ?? undefined,
    savepoint: options.savepoint ?? false,
  };

  return function <T extends (...args: unknown[]) => Promise<unknown>>(
    target: T,
    context: ClassMethodDecoratorContext | undefined
  ): T {
    const stepName =
      typeof context?.name === 'string' ? context.name : target.name;

    const wrapper = async function (
      this: unknown,
      ...args: Parameters<T>
    ): Promise<ReturnType<T>> {
      const ctx = ExecutionContext.current();
      const engine = ctx.getEngine();
      const lease = ctx.getLease();

      if (!engine) {
        throw new Error('No execution engine in context');
      }

      // Generate step ID
      const stepId = ctx.generateStepId(stepName);

      // Check idempotency
      const cachedResult = await engine.idempotency.checkCompleted(
        ctx.workflowId,
        stepId
      );

      if (cachedResult) {
        console.log(`Step ${stepId} already completed, returning cached result`);
        ctx.setState(cachedResult);
        return cachedResult as ReturnType<T>;
      }

      // Allocate attempt
      const attemptId = await engine.idempotency.allocateAttempt(
        ctx.workflowId,
        stepId,
        lease
      );

      // Write intention
      await engine.journal.append({
        eventId: crypto.randomUUID(),
        workflowId: ctx.workflowId,
        orgId: ctx.orgId,
        timestamp: new Date().toISOString(),
        eventType: 'step_intention',
        stepId,
        stepName,
        attemptId,
      });

      // Execute with timeout and retry
      const startTime = Date.now();
      let lastError: Error | null = null;
      let currentAttempt = attemptId;

      const executeStep = async (): Promise<unknown> => {
        if (config.timeout) {
          return executeWithTimeout(
            () => target.apply(this, args),
            config.timeout,
            ctx.workflowId,
            stepId,
            stepName
          );
        }
        return target.apply(this, args);
      };

      try {
        const result = await executeStep();
        const durationMs = Date.now() - startTime;

        // Extract new state
        const newState = ctx.extractState(result);
        const oldState = ctx.getState();

        // Compute delta (simplified)
        const delta = computeDelta(oldState, newState);

        // Write completion
        await engine.journal.append({
          eventId: crypto.randomUUID(),
          workflowId: ctx.workflowId,
          orgId: ctx.orgId,
          timestamp: new Date().toISOString(),
          eventType: 'step_completed',
          stepId,
          attemptId: currentAttempt,
          stateDelta: delta,
          durationMs,
        });

        // Mark completed
        await engine.idempotency.markCompleted(
          ctx.workflowId,
          stepId,
          currentAttempt,
          newState
        );

        // Update context
        ctx.setState(newState);
        ctx.incrementStep();

        // Checkpoint if configured
        if (config.checkpoint) {
          await engine.maybeSnapshot(newState);
        }

        // Savepoint if configured
        if (config.savepoint) {
          await ctx.createSavepoint();
        }

        return result as ReturnType<T>;
      } catch (error) {
        const durationMs = Date.now() - startTime;
        lastError = error as Error;

        // Log failure
        await engine.journal.append({
          eventId: crypto.randomUUID(),
          workflowId: ctx.workflowId,
          orgId: ctx.orgId,
          timestamp: new Date().toISOString(),
          eventType: 'step_failed',
          stepId,
          attemptId: currentAttempt,
          error: lastError.message,
        });

        // Check retry policy
        if (config.retry && shouldRetry(config.retry, currentAttempt, lastError)) {
          const backoff = calculateBackoff(config.retry, currentAttempt);
          console.log(`Retrying step ${stepId}, attempt ${currentAttempt + 1}`);
          await sleep(backoff * 1000);
          return wrapper.apply(this, args);
        }

        // Check max attempts
        if (config.retry && currentAttempt >= config.retry.maxAttempts) {
          throw new TooManyAttempts(
            ctx.workflowId,
            stepId,
            stepName,
            config.retry.maxAttempts,
            lastError.message
          );
        }

        // Wrap error
        throw new StepExecutionFailed(
          ctx.workflowId,
          stepId,
          stepName,
          currentAttempt,
          lastError
        );
      }
    } as T;

    // Attach metadata
    Object.defineProperty(wrapper, '__contd_step__', { value: true });
    Object.defineProperty(wrapper, '__contd_config__', { value: config });
    Object.defineProperty(wrapper, 'name', { value: stepName });

    return wrapper;
  };
}

// ============================================================================
// Helpers
// ============================================================================

async function executeWithTimeout<T>(
  fn: () => Promise<T>,
  timeoutMs: number,
  workflowId: string,
  stepId: string,
  stepName: string
): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(
        new StepTimeout(
          workflowId,
          stepId,
          stepName,
          timeoutMs / 1000,
          timeoutMs / 1000
        )
      );
    }, timeoutMs);

    fn()
      .then((result) => {
        clearTimeout(timer);
        resolve(result);
      })
      .catch((error) => {
        clearTimeout(timer);
        reject(error);
      });
  });
}

function computeDelta(
  oldState: WorkflowState,
  newState: WorkflowState
): Record<string, unknown> {
  const delta: Record<string, unknown> = {};

  // Compare variables
  for (const [key, value] of Object.entries(newState.variables)) {
    if (JSON.stringify(oldState.variables[key]) !== JSON.stringify(value)) {
      delta[key] = value;
    }
  }

  // Check for removed keys
  for (const key of Object.keys(oldState.variables)) {
    if (!(key in newState.variables)) {
      delta[key] = null;
    }
  }

  return delta;
}
