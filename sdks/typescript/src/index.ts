/**
 * Contd SDK for TypeScript/Node.js
 * Resumable workflows with exactly-once execution semantics
 */

// Types
export {
  WorkflowStatus,
  StepStatus,
  RetryPolicy,
  WorkflowConfig,
  StepConfig,
  WorkflowState,
  SavepointMetadata,
  SavepointInfo,
  WorkflowResult,
  StepResult,
  WorkflowStatusResponse,
  HealthCheck,
  WorkflowInput,
  BaseEvent,
  StepIntentionEvent,
  StepCompletedEvent,
  StepFailedEvent,
  SavepointCreatedEvent,
} from './types';

// Errors
export {
  ContdError,
  WorkflowLocked,
  NoActiveWorkflow,
  WorkflowNotFound,
  WorkflowAlreadyCompleted,
  StepError,
  StepTimeout,
  TooManyAttempts,
  StepExecutionFailed,
  IntegrityError,
  ChecksumMismatch,
  EventSequenceGap,
  SnapshotCorrupted,
  PersistenceError,
  JournalWriteError,
  LeaseAcquisitionFailed,
  SnapshotStorageError,
  RecoveryError,
  RecoveryFailed,
  InvalidSavepoint,
  ConfigurationError,
  InvalidRetryPolicy,
  WorkflowInterrupted,
} from './errors';

// Client
export { ContdClient, ClientConfig, StartWorkflowOptions } from './client';

// Context
export { ExecutionContext, ExecutionEngine, Lease } from './context';

// Decorators
export { workflow, step, WorkflowOptions, StepOptions } from './decorators';

// Registry
export { WorkflowRegistry } from './registry';

// Testing
export {
  ContdTestCase,
  MockExecutionEngine,
  WorkflowTestBuilder,
  StepExecution,
  WorkflowExecution,
} from './testing';
