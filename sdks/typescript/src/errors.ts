/**
 * Contd SDK Error Hierarchy
 * All exceptions inherit from ContdError for easy catching
 */

export interface ErrorDetails {
  [key: string]: unknown;
}

// ============================================================================
// Base Error
// ============================================================================

export class ContdError extends Error {
  public readonly workflowId?: string;
  public readonly details: ErrorDetails;

  constructor(message: string, workflowId?: string, details: ErrorDetails = {}) {
    super(ContdError.formatMessage(message, workflowId, details));
    this.name = 'ContdError';
    this.workflowId = workflowId;
    this.details = details;
    Object.setPrototypeOf(this, ContdError.prototype);
  }

  private static formatMessage(
    message: string,
    workflowId?: string,
    details?: ErrorDetails
  ): string {
    const parts = [message];
    if (workflowId) parts.push(`[workflow=${workflowId}]`);
    if (details && Object.keys(details).length > 0) {
      parts.push(`details=${JSON.stringify(details)}`);
    }
    return parts.join(' ');
  }
}

// ============================================================================
// Workflow Lifecycle Errors
// ============================================================================

export class WorkflowLocked extends ContdError {
  constructor(workflowId: string, ownerId?: string, expiresAt?: string) {
    const details: ErrorDetails = {};
    if (ownerId) details.currentOwner = ownerId;
    if (expiresAt) details.expiresAt = expiresAt;
    super('Workflow is locked by another executor', workflowId, details);
    this.name = 'WorkflowLocked';
    Object.setPrototypeOf(this, WorkflowLocked.prototype);
  }
}

export class NoActiveWorkflow extends ContdError {
  constructor(message = 'No active workflow context') {
    super(message);
    this.name = 'NoActiveWorkflow';
    Object.setPrototypeOf(this, NoActiveWorkflow.prototype);
  }
}

export class WorkflowNotFound extends ContdError {
  constructor(workflowId: string) {
    super('Workflow not found', workflowId);
    this.name = 'WorkflowNotFound';
    Object.setPrototypeOf(this, WorkflowNotFound.prototype);
  }
}

export class WorkflowAlreadyCompleted extends ContdError {
  constructor(workflowId: string, completedAt?: string) {
    const details: ErrorDetails = {};
    if (completedAt) details.completedAt = completedAt;
    super('Workflow has already completed', workflowId, details);
    this.name = 'WorkflowAlreadyCompleted';
    Object.setPrototypeOf(this, WorkflowAlreadyCompleted.prototype);
  }
}

// ============================================================================
// Step Execution Errors
// ============================================================================

export class StepError extends ContdError {
  public readonly stepId?: string;
  public readonly stepName?: string;
  public readonly attempt?: number;

  constructor(
    message: string,
    workflowId?: string,
    stepId?: string,
    stepName?: string,
    attempt?: number,
    details: ErrorDetails = {}
  ) {
    const fullDetails = { ...details };
    if (stepId) fullDetails.stepId = stepId;
    if (stepName) fullDetails.stepName = stepName;
    if (attempt !== undefined) fullDetails.attempt = attempt;
    super(message, workflowId, fullDetails);
    this.name = 'StepError';
    this.stepId = stepId;
    this.stepName = stepName;
    this.attempt = attempt;
    Object.setPrototypeOf(this, StepError.prototype);
  }
}

export class StepTimeout extends StepError {
  constructor(
    workflowId: string,
    stepId: string,
    stepName: string,
    timeoutSeconds: number,
    elapsedSeconds: number
  ) {
    super(
      `Step timed out after ${elapsedSeconds.toFixed(2)}s (limit: ${timeoutSeconds}s)`,
      workflowId,
      stepId,
      stepName,
      undefined,
      { timeoutSeconds, elapsedSeconds }
    );
    this.name = 'StepTimeout';
    Object.setPrototypeOf(this, StepTimeout.prototype);
  }
}

export class TooManyAttempts extends StepError {
  constructor(
    workflowId: string,
    stepId: string,
    stepName: string,
    maxAttempts: number,
    lastError?: string
  ) {
    const details: ErrorDetails = { maxAttempts };
    if (lastError) details.lastError = lastError;
    super(
      `Step exceeded ${maxAttempts} retry attempts`,
      workflowId,
      stepId,
      stepName,
      undefined,
      details
    );
    this.name = 'TooManyAttempts';
    Object.setPrototypeOf(this, TooManyAttempts.prototype);
  }
}

export class StepExecutionFailed extends StepError {
  public readonly originalError: Error;

  constructor(
    workflowId: string,
    stepId: string,
    stepName: string,
    attempt: number,
    originalError: Error
  ) {
    super(
      `Step execution failed: ${originalError.message}`,
      workflowId,
      stepId,
      stepName,
      attempt,
      { originalErrorType: originalError.name }
    );
    this.name = 'StepExecutionFailed';
    this.originalError = originalError;
    Object.setPrototypeOf(this, StepExecutionFailed.prototype);
  }
}

// ============================================================================
// Data Integrity Errors
// ============================================================================

export class IntegrityError extends ContdError {
  constructor(message: string, workflowId?: string, details?: ErrorDetails) {
    super(message, workflowId, details);
    this.name = 'IntegrityError';
    Object.setPrototypeOf(this, IntegrityError.prototype);
  }
}

export class ChecksumMismatch extends IntegrityError {
  constructor(
    workflowId: string,
    resourceType: string,
    expected: string,
    actual: string
  ) {
    super(`${resourceType} checksum mismatch`, workflowId, {
      resourceType,
      expectedChecksum: expected.substring(0, 16) + '...',
      actualChecksum: actual.substring(0, 16) + '...',
    });
    this.name = 'ChecksumMismatch';
    Object.setPrototypeOf(this, ChecksumMismatch.prototype);
  }
}

export class EventSequenceGap extends IntegrityError {
  constructor(workflowId: string, expectedSeq: number, actualSeq: number) {
    super(
      `Event sequence gap: expected ${expectedSeq}, got ${actualSeq}`,
      workflowId,
      {
        expectedSequence: expectedSeq,
        actualSequence: actualSeq,
        gapSize: actualSeq - expectedSeq,
      }
    );
    this.name = 'EventSequenceGap';
    Object.setPrototypeOf(this, EventSequenceGap.prototype);
  }
}

export class SnapshotCorrupted extends IntegrityError {
  constructor(workflowId: string, snapshotRef: string, reason: string) {
    super(`Snapshot corrupted: ${reason}`, workflowId, { snapshotRef, reason });
    this.name = 'SnapshotCorrupted';
    Object.setPrototypeOf(this, SnapshotCorrupted.prototype);
  }
}

// ============================================================================
// Persistence Errors
// ============================================================================

export class PersistenceError extends ContdError {
  constructor(message: string, workflowId?: string, details?: ErrorDetails) {
    super(message, workflowId, details);
    this.name = 'PersistenceError';
    Object.setPrototypeOf(this, PersistenceError.prototype);
  }
}

export class JournalWriteError extends PersistenceError {
  constructor(workflowId: string, eventType: string, reason: string) {
    super(`Failed to write ${eventType} event: ${reason}`, workflowId, {
      eventType,
    });
    this.name = 'JournalWriteError';
    Object.setPrototypeOf(this, JournalWriteError.prototype);
  }
}

export class LeaseAcquisitionFailed extends PersistenceError {
  constructor(workflowId: string, reason: string) {
    super(`Lease acquisition failed: ${reason}`, workflowId);
    this.name = 'LeaseAcquisitionFailed';
    Object.setPrototypeOf(this, LeaseAcquisitionFailed.prototype);
  }
}

export class SnapshotStorageError extends PersistenceError {
  constructor(workflowId: string, operation: string, reason: string) {
    super(`Snapshot ${operation} failed: ${reason}`, workflowId, { operation });
    this.name = 'SnapshotStorageError';
    Object.setPrototypeOf(this, SnapshotStorageError.prototype);
  }
}

// ============================================================================
// Recovery Errors
// ============================================================================

export class RecoveryError extends ContdError {
  constructor(message: string, workflowId?: string, details?: ErrorDetails) {
    super(message, workflowId, details);
    this.name = 'RecoveryError';
    Object.setPrototypeOf(this, RecoveryError.prototype);
  }
}

export class RecoveryFailed extends RecoveryError {
  public readonly recoverable: boolean;

  constructor(workflowId: string, reason: string, recoverable = false) {
    super(`Recovery failed: ${reason}`, workflowId, { recoverable });
    this.name = 'RecoveryFailed';
    this.recoverable = recoverable;
    Object.setPrototypeOf(this, RecoveryFailed.prototype);
  }
}

export class InvalidSavepoint extends RecoveryError {
  constructor(workflowId: string, savepointId: string, reason: string) {
    super(`Invalid savepoint: ${reason}`, workflowId, { savepointId });
    this.name = 'InvalidSavepoint';
    Object.setPrototypeOf(this, InvalidSavepoint.prototype);
  }
}

// ============================================================================
// Configuration Errors
// ============================================================================

export class ConfigurationError extends ContdError {
  constructor(message: string, configKey?: string) {
    const details: ErrorDetails = {};
    if (configKey) details.configKey = configKey;
    super(message, undefined, details);
    this.name = 'ConfigurationError';
    Object.setPrototypeOf(this, ConfigurationError.prototype);
  }
}

export class InvalidRetryPolicy extends ConfigurationError {
  constructor(reason: string) {
    super(`Invalid retry policy: ${reason}`, 'retryPolicy');
    this.name = 'InvalidRetryPolicy';
    Object.setPrototypeOf(this, InvalidRetryPolicy.prototype);
  }
}

// ============================================================================
// Testing Errors
// ============================================================================

export class WorkflowInterrupted extends ContdError {
  constructor(workflowId: string, stepNumber: number) {
    super(
      `Workflow interrupted at step ${stepNumber} for testing`,
      workflowId,
      { interruptedAtStep: stepNumber }
    );
    this.name = 'WorkflowInterrupted';
    Object.setPrototypeOf(this, WorkflowInterrupted.prototype);
  }
}
