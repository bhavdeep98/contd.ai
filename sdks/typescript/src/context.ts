/**
 * Execution Context
 * Thread-local context for workflow execution
 */

import { randomUUID } from 'crypto';
import { createHash } from 'crypto';
import { hostname } from 'os';
import { WorkflowState, SavepointMetadata } from './types';
import { NoActiveWorkflow } from './errors';

// AsyncLocalStorage for context propagation
import { AsyncLocalStorage } from 'async_hooks';

const contextStorage = new AsyncLocalStorage<ExecutionContext>();

function generateId(): string {
  return randomUUID();
}

function generateWorkflowId(): string {
  return `wf-${generateId()}`;
}

function getExecutorId(): string {
  return `${hostname()}-${randomUUID().substring(0, 8)}`;
}

function computeChecksum(state: WorkflowState): string {
  const hash = createHash('sha256');
  hash.update(JSON.stringify(state));
  return hash.digest('hex');
}

export interface Lease {
  workflowId: string;
  ownerId: string;
  expiresAt: Date;
}

export interface ExecutionEngine {
  restore(workflowId: string): Promise<WorkflowState>;
  completeWorkflow(workflowId: string): Promise<void>;
  maybeSnapshot(state: WorkflowState): Promise<void>;
  leaseManager: {
    acquire(workflowId: string, ownerId: string): Promise<Lease | null>;
    release(lease: Lease): Promise<void>;
    heartbeat(lease: Lease): Promise<void>;
    HEARTBEAT_INTERVAL: number;
  };
  journal: {
    append(event: unknown): Promise<void>;
  };
  idempotency: {
    checkCompleted(workflowId: string, stepId: string): Promise<WorkflowState | null>;
    allocateAttempt(workflowId: string, stepId: string, lease: Lease | null): Promise<number>;
    markCompleted(workflowId: string, stepId: string, attemptId: number, state: WorkflowState): Promise<void>;
  };
}

export class ExecutionContext {
  public readonly workflowId: string;
  public readonly orgId: string;
  public readonly workflowName: string;
  public readonly executorId: string;
  public tags: Record<string, string>;

  private _state: WorkflowState | null = null;
  private _stepCounter = 0;
  private _heartbeatInterval: NodeJS.Timeout | null = null;
  private _engine: ExecutionEngine | null = null;
  private _lease: Lease | null = null;

  constructor(
    workflowId: string,
    orgId: string,
    workflowName: string,
    executorId: string,
    tags?: Record<string, string>
  ) {
    this.workflowId = workflowId;
    this.orgId = orgId;
    this.workflowName = workflowName;
    this.executorId = executorId;
    this.tags = tags || {};
  }

  /**
   * Get current execution context
   */
  static current(): ExecutionContext {
    const ctx = contextStorage.getStore();
    if (!ctx) {
      throw new NoActiveWorkflow(
        'No workflow context found. Did you forget @workflow decorator?'
      );
    }
    return ctx;
  }

  /**
   * Run a function within this context
   */
  run<T>(fn: () => T | Promise<T>): T | Promise<T> {
    return contextStorage.run(this, fn);
  }

  /**
   * Create new context or prepare for resume
   */
  static getOrCreate(
    workflowId: string | undefined,
    workflowName: string,
    orgId?: string,
    tags?: Record<string, string>
  ): ExecutionContext {
    const id = workflowId || generateWorkflowId();
    const org = orgId || 'default';

    const ctx = new ExecutionContext(
      id,
      org,
      workflowName,
      getExecutorId(),
      tags
    );

    if (!workflowId) {
      // New workflow - create initial state
      const initialState: WorkflowState = {
        workflowId: id,
        stepNumber: 0,
        variables: {},
        metadata: {
          workflowName,
          startedAt: new Date().toISOString(),
          tags: tags || {},
        },
        version: '1.0',
        checksum: '',
        orgId: org,
      };
      initialState.checksum = computeChecksum(initialState);
      ctx._state = initialState;
    }

    return ctx;
  }

  /**
   * Check if workflow is being resumed
   */
  isResuming(): boolean {
    return this._state === null;
  }

  /**
   * Get current workflow state
   */
  getState(): WorkflowState {
    if (!this._state) {
      throw new Error('State not initialized. Call restore() or init.');
    }
    return this._state;
  }

  /**
   * Set workflow state
   */
  setState(state: WorkflowState): void {
    this._state = state;
    this._stepCounter = state.stepNumber;
  }

  /**
   * Increment step counter
   */
  incrementStep(): void {
    this._stepCounter++;
  }

  /**
   * Generate deterministic step ID
   */
  generateStepId(stepName: string): string {
    return `${stepName}_${this._stepCounter}`;
  }

  /**
   * Extract new state from step result
   */
  extractState(result: unknown): WorkflowState {
    if (this.isWorkflowState(result)) {
      return result;
    }

    const currentVars = { ...this._state!.variables };

    if (typeof result === 'object' && result !== null) {
      Object.assign(currentVars, result);
    }

    const newState: WorkflowState = {
      workflowId: this._state!.workflowId,
      stepNumber: this._state!.stepNumber + 1,
      variables: currentVars,
      metadata: this._state!.metadata,
      version: this._state!.version,
      checksum: '',
      orgId: this.orgId,
    };
    newState.checksum = computeChecksum(newState);

    return newState;
  }

  /**
   * Set engine reference
   */
  setEngine(engine: ExecutionEngine): void {
    this._engine = engine;
  }

  /**
   * Get engine reference
   */
  getEngine(): ExecutionEngine | null {
    return this._engine;
  }

  /**
   * Set lease reference
   */
  setLease(lease: Lease | null): void {
    this._lease = lease;
  }

  /**
   * Get lease reference
   */
  getLease(): Lease | null {
    return this._lease;
  }

  /**
   * Start background heartbeat
   */
  startHeartbeat(lease: Lease, engine: ExecutionEngine): void {
    this._lease = lease;
    this._engine = engine;

    this._heartbeatInterval = setInterval(async () => {
      try {
        await engine.leaseManager.heartbeat(lease);
      } catch (error) {
        console.error(`Heartbeat failed for ${this.workflowId}:`, error);
        this.stopHeartbeat();
      }
    }, engine.leaseManager.HEARTBEAT_INTERVAL);
  }

  /**
   * Stop background heartbeat
   */
  stopHeartbeat(): void {
    if (this._heartbeatInterval) {
      clearInterval(this._heartbeatInterval);
      this._heartbeatInterval = null;
    }
  }

  /**
   * Create rich savepoint with epistemic metadata
   */
  async createSavepoint(metadata?: SavepointMetadata): Promise<string> {
    const savepointId = generateId();
    const meta = metadata || (this._state?.variables._savepoint_metadata as SavepointMetadata);

    if (this._engine) {
      await this._engine.journal.append({
        eventId: generateId(),
        workflowId: this.workflowId,
        orgId: this.orgId,
        timestamp: new Date().toISOString(),
        eventType: 'savepoint_created',
        savepointId,
        stepNumber: this._state?.stepNumber || 0,
        goalSummary: meta?.goalSummary || '',
        currentHypotheses: meta?.hypotheses || [],
        openQuestions: meta?.questions || [],
        decisionLog: meta?.decisions || [],
        nextStep: meta?.nextStep || '',
        snapshotRef: '',
      });
    }

    console.log(`Created savepoint ${savepointId} at step ${this._state?.stepNumber}`);
    return savepointId;
  }

  /**
   * Update workflow tags
   */
  updateTags(newTags: Record<string, string>): void {
    this.tags = { ...this.tags, ...newTags };

    if (this._state) {
      const currentMetadata = { ...this._state.metadata };
      const currentTags = (currentMetadata.tags as Record<string, string>) || {};
      currentMetadata.tags = { ...currentTags, ...newTags };

      this._state = {
        ...this._state,
        metadata: currentMetadata,
      };
    }
  }

  private isWorkflowState(value: unknown): value is WorkflowState {
    return (
      typeof value === 'object' &&
      value !== null &&
      'workflowId' in value &&
      'stepNumber' in value &&
      'variables' in value
    );
  }
}
