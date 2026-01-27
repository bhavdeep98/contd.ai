package contd

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// ClientConfig configures the Contd client
type ClientConfig struct {
	APIKey  string
	BaseURL string
	Timeout time.Duration
	Retries int
}

// Client is the HTTP client for remote workflow execution
type Client struct {
	apiKey     string
	baseURL    string
	httpClient *http.Client
	retries    int
}

// NewClient creates a new Contd client
func NewClient(config ClientConfig) *Client {
	baseURL := config.BaseURL
	if baseURL == "" {
		baseURL = "https://api.contd.ai"
	}

	timeout := config.Timeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}

	retries := config.Retries
	if retries == 0 {
		retries = 3
	}

	return &Client{
		apiKey:  config.APIKey,
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: timeout,
		},
		retries: retries,
	}
}

// StartWorkflowInput contains parameters for starting a workflow
type StartWorkflowInput struct {
	WorkflowName string                 `json:"workflow_name"`
	Input        map[string]interface{} `json:"input"`
	Config       *WorkflowConfig        `json:"config,omitempty"`
}

// StartWorkflow starts a new workflow and returns the workflow ID
func (c *Client) StartWorkflow(ctx context.Context, input StartWorkflowInput) (string, error) {
	body, err := json.Marshal(input)
	if err != nil {
		return "", fmt.Errorf("failed to marshal input: %w", err)
	}

	resp, err := c.doRequest(ctx, "POST", "/v1/workflows", body)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		WorkflowID string `json:"workflow_id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	return result.WorkflowID, nil
}

// GetStatus retrieves the status of a workflow
func (c *Client) GetStatus(ctx context.Context, workflowID string) (*WorkflowStatusResponse, error) {
	resp, err := c.doRequest(ctx, "GET", fmt.Sprintf("/v1/workflows/%s", workflowID), nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result WorkflowStatusResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &result, nil
}

// Resume resumes an interrupted workflow
func (c *Client) Resume(ctx context.Context, workflowID string) (string, error) {
	resp, err := c.doRequest(ctx, "POST", fmt.Sprintf("/v1/workflows/%s/resume", workflowID), nil)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		Status string `json:"status"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	return result.Status, nil
}

// Cancel cancels a running workflow
func (c *Client) Cancel(ctx context.Context, workflowID string) error {
	resp, err := c.doRequest(ctx, "POST", fmt.Sprintf("/v1/workflows/%s/cancel", workflowID), nil)
	if err != nil {
		return err
	}
	resp.Body.Close()
	return nil
}

// GetSavepoints retrieves all savepoints for a workflow
func (c *Client) GetSavepoints(ctx context.Context, workflowID string) ([]SavepointInfo, error) {
	resp, err := c.doRequest(ctx, "GET", fmt.Sprintf("/v1/workflows/%s/savepoints", workflowID), nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result struct {
		Savepoints []SavepointInfo `json:"savepoints"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return result.Savepoints, nil
}

// TimeTravel restores a workflow to a specific savepoint
func (c *Client) TimeTravel(ctx context.Context, workflowID, savepointID string) (string, error) {
	body, err := json.Marshal(map[string]string{"savepoint_id": savepointID})
	if err != nil {
		return "", fmt.Errorf("failed to marshal input: %w", err)
	}

	resp, err := c.doRequest(ctx, "POST", fmt.Sprintf("/v1/workflows/%s/time-travel", workflowID), body)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		NewWorkflowID string `json:"new_workflow_id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	return result.NewWorkflowID, nil
}

// Health performs a health check
func (c *Client) Health(ctx context.Context) (*HealthCheck, error) {
	resp, err := c.doRequest(ctx, "GET", "/health", nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result HealthCheck
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &result, nil
}

// ListWorkflowsInput contains parameters for listing workflows
type ListWorkflowsInput struct {
	Status string
	Tags   map[string]string
	Limit  int
	Offset int
}

// ListWorkflowsOutput contains the result of listing workflows
type ListWorkflowsOutput struct {
	Workflows []WorkflowStatusResponse `json:"workflows"`
	Total     int                      `json:"total"`
}

// ListWorkflows lists workflows with optional filters
func (c *Client) ListWorkflows(ctx context.Context, input ListWorkflowsInput) (*ListWorkflowsOutput, error) {
	params := url.Values{}
	if input.Status != "" {
		params.Set("status", input.Status)
	}
	if input.Limit > 0 {
		params.Set("limit", fmt.Sprintf("%d", input.Limit))
	}
	if input.Offset > 0 {
		params.Set("offset", fmt.Sprintf("%d", input.Offset))
	}
	for k, v := range input.Tags {
		params.Set(fmt.Sprintf("tag.%s", k), v)
	}

	path := "/v1/workflows"
	if len(params) > 0 {
		path += "?" + params.Encode()
	}

	resp, err := c.doRequest(ctx, "GET", path, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result ListWorkflowsOutput
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &result, nil
}

func (c *Client) doRequest(ctx context.Context, method, path string, body []byte) (*http.Response, error) {
	var bodyReader io.Reader
	if body != nil {
		bodyReader = bytes.NewReader(body)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}

	if resp.StatusCode >= 400 {
		defer resp.Body.Close()
		return nil, c.handleError(resp)
	}

	return resp, nil
}

func (c *Client) handleError(resp *http.Response) error {
	body, _ := io.ReadAll(resp.Body)

	var errResp struct {
		Message    string `json:"message"`
		WorkflowID string `json:"workflow_id"`
	}
	json.Unmarshal(body, &errResp)

	message := errResp.Message
	if message == "" {
		message = string(body)
	}

	switch resp.StatusCode {
	case 404:
		return NewWorkflowNotFound(errResp.WorkflowID)
	case 409:
		return NewWorkflowLocked(errResp.WorkflowID, "", "")
	case 500:
		return NewPersistenceError(message, errResp.WorkflowID, nil)
	default:
		return NewContdError(message, errResp.WorkflowID, nil)
	}
}
