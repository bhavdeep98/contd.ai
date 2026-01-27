/**
 * Contd SDK Testing Utilities
 * Test harnesses and mocks for workflow testing
 */

import { WorkflowState, BaseEvent } from './types';
import { WorkflowInterrupted } from './errors';
import { ExecutionContext, ExecutionEngine, Lease } from './context';
import { WorkflowRegistry } from './registry';

// ============================================================================
// Step and Workflow Execution Records
// ============================================================================

export interface StepExecution {
  stepName: string;
  stepId: string;
  attempt: number;
  startedAt: Date;
  completedAt?: Date;
  durationMs: number;
  result?: unknown;
  error?: string;
  wasCached: boolean;
}

export interface WorkflowExecution {
  workflowId: string;
  workflowName: string;
  startedAt: Date;
  completedAt?: Date;
  status: 'running' | 'completed' | 'interrupted' | 'failed';
  steps: StepExecution[];
  finalState?: WorkflowState;
  error?: string;
  interruptedAtStep?: number;
}

// ============================================================================
// Mock Execution Engine
// ============================================================================

export class MockExecutionEngine implements ExecutionEngine {
  private _interruptAtStep?: number;
  private _failAtStep?: number;
  private _failWith?: new (message: string) => Error;
  private _recordedEvents: BaseEvent[] = [];
  private _stepCounter = 0;
  private _states: Map<string, WorkflowState> = new Map();
  private _completedSteps: Map<string, WorkflowState> = new Map();

  leaseManager = {
    acquire: async (workflowId: string, ownerId: string): Promise<Lease | null> => {
      return {
        workflowId,
        ownerId,
        expiresAt: new Date(Date.now() + 60000),
      };
    },
    release: async (_lease: Lease): Promise<void> => {},
    heartbeat: async (_lease: Lease): Promise<void> => {},
    HEARTBEAT_INTERVAL: 10000,
  };

  journal = {
    append: async (event: unknown): Promise<void> => {
      this._recordedEvents.push(event as BaseEvent);
    },
  };

  idempotency = {
    checkCompleted: async (
      workflowId: string,
      stepId: string
    ): Promise<WorkflowState | null> => {
      return this._completedSteps.get(`${workflowId}:${stepId}`) || null;
    },
    allocateAttempt: async (
      _workflowId: string,
      _stepId: string,
      _lease: Lease | null
    ): Promise<number> => {
      return ++this._stepCounter;
    },
    markCompleted: async (
      workflowId: string,
      stepId: string,
      _attemptId: number,
      state: WorkflowState
    ): Promise<void> => {
      this._completedSteps.set(`${workflowId}:${stepId}`, state);
    },
  };

  async restore(workflowId: string): Promise<WorkflowState> {
    const state = this._states.get(workflowId);
    if (!state) {
      return {
        workflowId,
        stepNumber: 0,
        variables: {},
        metadata: {},
        version: '1.0',
        checksum: '',
        orgId: 'default',
      };
    }
    return state;
  }

  async completeWorkflow(workflowId: string): Promise<void> {
    const state = this._states.get(workflowId);
    if (state) {
      state.metadata.completedAt = new Date().toISOString();
    }
  }

  async maybeSnapshot(state: WorkflowState): Promise<void> {
    this._states.set(state.workflowId, state);
  }

  /**
   * Configure interruption at specific step
   */
  setInterruptAt(stepNumber: number): void {
    this._interruptAtStep = stepNumber;
  }

  /**
   * Configure failure injection at specific step
   */
  setFailAt(
    stepNumber: number,
    exceptionType: new (message: string) => Error = Error
  ): void {
    this._failAtStep = stepNumber;
    this._failWith = exceptionType;
  }

  /**
   * Check if workflow should be interrupted
   */
  checkInterrupt(stepNumber: number, workflowId: string): void {
    if (
      this._interruptAtStep !== undefined &&
      stepNumber >= this._interruptAtStep
    ) {
      throw new WorkflowInterrupted(workflowId, stepNumber);
    }
  }

  /**
   * Check if failure should be injected
   */
  checkFailure(stepNumber: number): void {
    if (this._failAtStep !== undefined && stepNumber === this._failAtStep) {
      const ErrorClass = this._failWith || Error;
      throw new ErrorClass(`Injected failure at step ${stepNumber}`);
    }
  }

  /**
   * Get recorded events
   */
  getRecordedEvents(): BaseEvent[] {
    return [...this._recordedEvents];
  }

  /**
   * Clear recorded events
   */
  clearRecordedEvents(): void {
    this._recordedEvents = [];
  }

  /**
   * Reset all mock state
   */
  reset(): void {
    this._interruptAtStep = undefined;
    this._failAtStep = undefined;
    this._failWith = undefined;
    this._recordedEvents = [];
    this._stepCounter = 0;
    this._states.clear();
    this._completedSteps.clear();
  }
}

// ============================================================================
// Test Case Helper
// ============================================================================

export class ContdTestCase {
  public engine: MockExecutionEngine;
  public executions: WorkflowExecution[] = [];
  public currentExecution?: WorkflowExecution;

  constructor() {
    this.engine = new MockExecutionEngine();
  }

  /**
   * Set up test fixtures
   */
  setUp(): void {
    this.engine.reset();
    this.executions = [];
    this.currentExecution = undefined;
  }

  /**
   * Tear down test fixtures
   */
  tearDown(): void {
    this.engine.reset();
  }

  /**
   * Run a workflow with optional interruption or failure injection
   */
  async runWorkflow<T>(
    workflowFn: (...args: unknown[]) => Promise<T>,
    options: {
      args?: unknown[];
      interruptAtStep?: number;
      failAtStep?: number;
      failWith?: new (message: string) => Error;
    } = {}
  ): Promise<T | undefined> {
    // Configure mock engine
    if (options.interruptAtStep !== undefined) {
      this.engine.setInterruptAt(options.interruptAtStep);
    }
    if (options.failAtStep !== undefined) {
      this.engine.setFailAt(options.failAtStep, options.failWith);
    }

    // Create execution record
    const execution: WorkflowExecution = {
      workflowId: '',
      workflowName: workflowFn.name,
      startedAt: new Date(),
      status: 'running',
      steps: [],
    };
    this.currentExecution = execution;
    this.executions.push(execution);

    try {
      const result = await workflowFn(...(options.args || []));
      execution.status = 'completed';
      execution.completedAt = new Date();
      return result;
    } catch (error) {
      if (error instanceof WorkflowInterrupted) {
        execution.status = 'interrupted';
        execution.interruptedAtStep = error.details.interruptedAtStep as number;
        return undefined;
      }
      execution.status = 'failed';
      execution.error = (error as Error).message;
      execution.completedAt = new Date();
      throw error;
    }
  }

  /**
   * Resume an interrupted workflow
   */
  async resumeWorkflow<T>(
    workflowFn?: (...args: unknown[]) => Promise<T>,
    options: { args?: unknown[] } = {}
  ): Promise<T | undefined> {
    // Clear interrupt setting
    this.engine.reset();

    if (!workflowFn && this.currentExecution) {
      workflowFn = WorkflowRegistry.get(
        this.currentExecution.workflowName
      ) as typeof workflowFn;
    }

    if (!workflowFn) {
      throw new Error('No workflow function provided');
    }

    return this.runWorkflow(workflowFn, { args: options.args });
  }

  // ========================================================================
  // Assertions
  // ========================================================================

  assertCompleted(message = ''): void {
    if (!this.currentExecution) {
      throw new Error('No workflow execution to check');
    }
    if (this.currentExecution.status !== 'completed') {
      throw new Error(
        `Workflow not completed: status=${this.currentExecution.status}. ${message}`
      );
    }
  }

  assertInterrupted(atStep?: number, message = ''): void {
    if (!this.currentExecution) {
      throw new Error('No workflow execution to check');
    }
    if (this.currentExecution.status !== 'interrupted') {
      throw new Error(
        `Workflow not interrupted: status=${this.currentExecution.status}. ${message}`
      );
    }
    if (
      atStep !== undefined &&
      this.currentExecution.interruptedAtStep !== atStep
    ) {
      throw new Error(
        `Interrupted at wrong step: expected=${atStep}, actual=${this.currentExecution.interruptedAtStep}. ${message}`
      );
    }
  }

  assertFailed(errorContains?: string, message = ''): void {
    if (!this.currentExecution) {
      throw new Error('No workflow execution to check');
    }
    if (this.currentExecution.status !== 'failed') {
      throw new Error(
        `Workflow not failed: status=${this.currentExecution.status}. ${message}`
      );
    }
    if (
      errorContains &&
      !this.currentExecution.error?.includes(errorContains)
    ) {
      throw new Error(
        `Error message doesn't contain '${errorContains}': actual='${this.currentExecution.error}'. ${message}`
      );
    }
  }

  assertStepCount(expected: number, message = ''): void {
    if (!this.currentExecution) {
      throw new Error('No workflow execution to check');
    }
    const actual = this.currentExecution.steps.length;
    if (actual !== expected) {
      throw new Error(
        `Step count mismatch: expected=${expected}, actual=${actual}. ${message}`
      );
    }
  }

  assertEventCount(expected: number, eventType?: string, message = ''): void {
    let events = this.engine.getRecordedEvents();
    if (eventType) {
      events = events.filter((e) => e.eventType === eventType);
    }
    if (events.length !== expected) {
      throw new Error(
        `Event count mismatch: expected=${expected}, actual=${events.length}. ${message}`
      );
    }
  }

  // ========================================================================
  // Utilities
  // ========================================================================

  getEvents(eventType?: string): BaseEvent[] {
    let events = this.engine.getRecordedEvents();
    if (eventType) {
      events = events.filter((e) => e.eventType === eventType);
    }
    return events;
  }

  getFinalState(): WorkflowState | undefined {
    return this.currentExecution?.finalState;
  }

  printExecutionSummary(): void {
    if (!this.currentExecution) {
      console.log('No execution to summarize');
      return;
    }

    const ex = this.currentExecution;
    console.log('\n' + '='.repeat(50));
    console.log(`Workflow: ${ex.workflowName}`);
    console.log(`Status: ${ex.status}`);
    console.log(`Steps: ${ex.steps.length}`);
    if (ex.interruptedAtStep !== undefined) {
      console.log(`Interrupted at: step ${ex.interruptedAtStep}`);
    }
    if (ex.error) {
      console.log(`Error: ${ex.error}`);
    }
    console.log(`Events recorded: ${this.engine.getRecordedEvents().length}`);
    console.log('='.repeat(50) + '\n');
  }
}

// ============================================================================
// Fluent Test Builder
// ============================================================================

export class WorkflowTestBuilder<T> {
  private workflowFn: (...args: unknown[]) => Promise<T>;
  private testCase: ContdTestCase;
  private _args: unknown[] = [];
  private _interruptAt?: number;
  private _failAt?: number;
  private _failWith?: new (message: string) => Error;

  constructor(workflowFn: (...args: unknown[]) => Promise<T>) {
    this.workflowFn = workflowFn;
    this.testCase = new ContdTestCase();
    this.testCase.setUp();
  }

  withInput(...args: unknown[]): this {
    this._args = args;
    return this;
  }

  interruptAt(step: number): this {
    this._interruptAt = step;
    return this;
  }

  failAt(step: number, exception?: new (message: string) => Error): this {
    this._failAt = step;
    this._failWith = exception;
    return this;
  }

  async run(): Promise<this> {
    await this.testCase.runWorkflow(this.workflowFn, {
      args: this._args,
      interruptAtStep: this._interruptAt,
      failAtStep: this._failAt,
      failWith: this._failWith,
    });
    this._interruptAt = undefined;
    this._failAt = undefined;
    return this;
  }

  async resume(): Promise<this> {
    await this.testCase.resumeWorkflow(this.workflowFn, { args: this._args });
    return this;
  }

  assertCompleted(): this {
    this.testCase.assertCompleted();
    return this;
  }

  assertInterrupted(atStep?: number): this {
    this.testCase.assertInterrupted(atStep);
    return this;
  }

  assertFailed(errorContains?: string): this {
    this.testCase.assertFailed(errorContains);
    return this;
  }

  cleanup(): void {
    this.testCase.tearDown();
  }
}
