class ContdError(Exception):
    """Base exception"""
    pass

class WorkflowLocked(ContdError):
    """Workflow is locked by another executor"""
    pass

class NoActiveWorkflow(ContdError):
    """No workflow context found"""
    pass

class StepTimeout(ContdError):
    """Step exceeded timeout"""
    pass

class WorkflowInterrupted(ContdError):
    """Workflow was interrupted (test utility)"""
    pass

class IntegrityError(ContdError):
    """Data corruption detected"""
    pass

class TooManyAttempts(ContdError):
    """Step exceeded max retry attempts"""
    pass
