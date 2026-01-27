/**
 * Workflow Registry
 * Central registry for workflow functions
 */

type WorkflowFunction = (...args: unknown[]) => Promise<unknown>;

export class WorkflowRegistry {
  private static workflows: Map<string, WorkflowFunction> = new Map();

  /**
   * Register a workflow function
   */
  static register(name: string, fn: WorkflowFunction): void {
    this.workflows.set(name, fn);
  }

  /**
   * Get a workflow function by name
   */
  static get(name: string): WorkflowFunction | undefined {
    return this.workflows.get(name);
  }

  /**
   * List all registered workflows
   */
  static listAll(): Map<string, WorkflowFunction> {
    return new Map(this.workflows);
  }

  /**
   * Check if a workflow is registered
   */
  static has(name: string): boolean {
    return this.workflows.has(name);
  }

  /**
   * Clear all registered workflows (for testing)
   */
  static clear(): void {
    this.workflows.clear();
  }

  /**
   * Get workflow names
   */
  static names(): string[] {
    return Array.from(this.workflows.keys());
  }
}
