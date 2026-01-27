/**
 * Contd SDK Types
 * Type definitions for workflows, steps, and configuration
 */

// ============================================================================
// Enums
// ============================================================================

export enum WorkflowStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  SUSPENDED = 'suspended',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum StepStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  SKIPPED = 'skipped',
}

// ============================================================================
// Core Types
// ============================================================================

export interface RetryPolicy {
  maxAttempts: number;
  backoffBase: number;
  backoffMax: number;
  backoffJitter: number;
  retryableErrors?: string[];
}

export interface WorkflowConfig {
  workflowId?: string;
  maxDuration?: number; // milliseconds
  retryPolicy?: RetryPolicy;
  tags?: Record<string, string>;
  orgId?: string;
}

export interface StepConfig {
  checkpoint?: boolean;
  idempotencyKey?: string | ((args: unknown[]) => string);
  retry?: RetryPolicy;
  timeout?: number; // milliseconds
  savepoint?: boolean;
}

export interface WorkflowState {
  workflowId: string;
  stepNumber: number;
  variables: Record<string, unknown>;
  metadata: Record<string, unknown>;
  version: string;
  checksum: string;
  orgId: string;
}

// ============================================================================
// Savepoint Types
// ============================================================================

export interface SavepointMetadata {
  goalSummary: string;
  hypotheses: string[];
  questions: string[];
  decisions: Array<{
    decision: string;
    rationale: string;
    alternatives?: string[];
  }>;
  nextStep: string;
}

export interface SavepointInfo {
  savepointId: string;
  workflowId: string;
  stepNumber: number;
  createdAt: string;
  metadata: SavepointMetadata;
  snapshotSizeBytes?: number;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface WorkflowResult {
  workflowId: string;
  status: WorkflowStatus;
  result?: Record<string, unknown>;
  error?: string;
  startedAt: string;
  completedAt?: string;
  durationMs?: number;
  stepCount: number;
}

export interface StepResult {
  stepId: string;
  stepName: string;
  status: StepStatus;
  attempt: number;
  result?: unknown;
  error?: string;
  durationMs: number;
  wasCached: boolean;
}

export interface WorkflowStatusResponse {
  workflowId: string;
  orgId: string;
  status: WorkflowStatus;
  currentStep: number;
  totalSteps?: number;
  hasLease: boolean;
  leaseOwner?: string;
  leaseExpiresAt?: string;
  eventCount: number;
  snapshotCount: number;
  latestSnapshotStep?: number;
  savepoints: SavepointInfo[];
}

export interface HealthCheck {
  status: string;
  version: string;
  components: Record<string, string>;
}

// ============================================================================
// Input Types
// ============================================================================

export interface WorkflowInput {
  workflowName: string;
  inputData?: Record<string, unknown>;
  tags?: Record<string, string>;
  idempotencyKey?: string;
}

// ============================================================================
// Event Types
// ============================================================================

export interface BaseEvent {
  eventId: string;
  workflowId: string;
  orgId: string;
  timestamp: string;
  eventType: string;
}

export interface StepIntentionEvent extends BaseEvent {
  eventType: 'step_intention';
  stepId: string;
  stepName: string;
  attemptId: number;
}

export interface StepCompletedEvent extends BaseEvent {
  eventType: 'step_completed';
  stepId: string;
  attemptId: number;
  stateDelta: Record<string, unknown>;
  durationMs: number;
}

export interface StepFailedEvent extends BaseEvent {
  eventType: 'step_failed';
  stepId: string;
  attemptId: number;
  error: string;
}

export interface SavepointCreatedEvent extends BaseEvent {
  eventType: 'savepoint_created';
  savepointId: string;
  stepNumber: number;
  goalSummary: string;
  currentHypotheses: string[];
  openQuestions: string[];
  decisionLog: Array<Record<string, unknown>>;
  nextStep: string;
  snapshotRef: string;
}
