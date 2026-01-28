/**
 * Contd Client
 * HTTP client for remote workflow execution
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  WorkflowConfig,
  WorkflowStatusResponse,
  SavepointInfo,
  HealthCheck,
} from './types';
import {
  ContdError,
  WorkflowNotFound,
  WorkflowLocked,
  PersistenceError,
} from './errors';

export interface ClientConfig {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  retries?: number;
}

export interface StartWorkflowOptions {
  workflowName: string;
  input: Record<string, unknown>;
  config?: WorkflowConfig;
}

export class ContdClient {
  private readonly client: AxiosInstance;
  private readonly apiKey: string;
  private readonly retries: number;

  constructor(config: ClientConfig) {
    this.apiKey = config.apiKey;
    this.retries = config.retries ?? 3;

    this.client = axios.create({
      baseURL: config.baseUrl ?? 'https://api.contd.ai',
      timeout: config.timeout ?? 30000,
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json',
      },
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => this.handleError(error)
    );
  }

  /**
   * Start a new workflow
   */
  async startWorkflow(options: StartWorkflowOptions): Promise<string> {
    const response = await this.client.post('/v1/workflows', {
      workflow_name: options.workflowName,
      input: options.input,
      config: options.config ? this.serializeConfig(options.config) : undefined,
    });
    return response.data.workflow_id;
  }

  /**
   * Get workflow status
   */
  async getStatus(workflowId: string): Promise<WorkflowStatusResponse> {
    const response = await this.client.get(`/v1/workflows/${workflowId}`);
    return this.deserializeStatus(response.data);
  }

  /**
   * Resume an interrupted workflow
   */
  async resume(workflowId: string): Promise<string> {
    const response = await this.client.post(
      `/v1/workflows/${workflowId}/resume`
    );
    return response.data.status;
  }

  /**
   * Cancel a running workflow
   */
  async cancel(workflowId: string): Promise<void> {
    await this.client.post(`/v1/workflows/${workflowId}/cancel`);
  }

  /**
   * Get all savepoints for a workflow
   */
  async getSavepoints(workflowId: string): Promise<SavepointInfo[]> {
    const response = await this.client.get(
      `/v1/workflows/${workflowId}/savepoints`
    );
    return response.data.savepoints.map(this.deserializeSavepoint);
  }

  /**
   * Time travel to a specific savepoint
   */
  async timeTravel(workflowId: string, savepointId: string): Promise<string> {
    const response = await this.client.post(
      `/v1/workflows/${workflowId}/time-travel`,
      { savepoint_id: savepointId }
    );
    return response.data.new_workflow_id;
  }

  /**
   * Health check
   */
  async health(): Promise<HealthCheck> {
    const response = await this.client.get('/health');
    return response.data;
  }

  /**
   * List workflows with optional filters
   */
  async listWorkflows(options?: {
    status?: string;
    tags?: Record<string, string>;
    limit?: number;
    offset?: number;
  }): Promise<{ workflows: WorkflowStatusResponse[]; total: number }> {
    const params = new URLSearchParams();
    if (options?.status) params.append('status', options.status);
    if (options?.limit) params.append('limit', options.limit.toString());
    if (options?.offset) params.append('offset', options.offset.toString());
    if (options?.tags) {
      Object.entries(options.tags).forEach(([k, v]) => {
        params.append(`tag.${k}`, v);
      });
    }

    const response = await this.client.get(`/v1/workflows?${params.toString()}`);
    return {
      workflows: response.data.workflows.map(this.deserializeStatus),
      total: response.data.total,
    };
  }

  // ========================================================================
  // Private helpers
  // ========================================================================

  private serializeConfig(config: WorkflowConfig): Record<string, unknown> {
    return {
      workflow_id: config.workflowId,
      max_duration: config.maxDuration,
      retry_policy: config.retryPolicy
        ? {
            max_attempts: config.retryPolicy.maxAttempts,
            backoff_base: config.retryPolicy.backoffBase,
            backoff_max: config.retryPolicy.backoffMax,
            backoff_jitter: config.retryPolicy.backoffJitter,
          }
        : undefined,
      tags: config.tags,
      org_id: config.orgId,
    };
  }

  private deserializeStatus(data: Record<string, unknown>): WorkflowStatusResponse {
    return {
      workflowId: data.workflow_id as string,
      orgId: data.org_id as string,
      status: data.status as WorkflowStatusResponse['status'],
      currentStep: data.current_step as number,
      totalSteps: data.total_steps as number | undefined,
      hasLease: data.has_lease as boolean,
      leaseOwner: data.lease_owner as string | undefined,
      leaseExpiresAt: data.lease_expires_at as string | undefined,
      eventCount: data.event_count as number,
      snapshotCount: data.snapshot_count as number,
      latestSnapshotStep: data.latest_snapshot_step as number | undefined,
      savepoints: ((data.savepoints as unknown[]) || []).map(
        (sp) => this.deserializeSavepoint(sp as Record<string, unknown>)
      ),
    };
  }

  private deserializeSavepoint(data: Record<string, unknown>): SavepointInfo {
    const metadata = data.metadata as Record<string, unknown> | undefined;
    return {
      savepointId: data.savepoint_id as string,
      workflowId: data.workflow_id as string,
      stepNumber: data.step_number as number,
      createdAt: data.created_at as string,
      metadata: {
        goalSummary: (metadata?.goal_summary as string) || '',
        hypotheses: (metadata?.hypotheses as string[]) || [],
        questions: (metadata?.questions as string[]) || [],
        decisions: ((metadata?.decisions as Array<Record<string, unknown>>) || []).map(d => ({
          decision: (d.decision as string) || '',
          rationale: (d.rationale as string) || '',
          alternatives: d.alternatives as string[] | undefined,
        })),
        nextStep: (metadata?.next_step as string) || '',
      },
      snapshotSizeBytes: data.snapshot_size_bytes as number | undefined,
    };
  }

  private handleError(error: AxiosError): never {
    const status = error.response?.status;
    const data = error.response?.data as Record<string, unknown> | undefined;
    const message = (data?.message as string) || error.message;
    const workflowId = data?.workflow_id as string | undefined;

    if (status === 404) {
      throw new WorkflowNotFound(workflowId || 'unknown');
    }
    if (status === 409) {
      throw new WorkflowLocked(workflowId || 'unknown');
    }
    if (status === 500) {
      throw new PersistenceError(message, workflowId);
    }

    throw new ContdError(message, workflowId);
  }
}
