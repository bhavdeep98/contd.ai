"""
Example 11: Code Review Agent

Automated code review workflow using AI.
Demonstrates multi-step analysis with savepoints.
"""

from contd.sdk import workflow, step, StepConfig, ExecutionContext
from typing import List, Dict
import time


@step()
def fetch_pull_request(pr_url: str) -> dict:
    """Fetch pull request details."""
    print(f"Fetching PR: {pr_url}")
    
    # Simulate PR fetch (in production: use GitHub API)
    return {
        "pr_id": "PR-123",
        "title": "Add user authentication",
        "author": "developer@example.com",
        "base_branch": "main",
        "head_branch": "feature/auth",
        "files_changed": [
            {
                "path": "src/auth/login.py",
                "additions": 45,
                "deletions": 5,
                "patch": """
+def login(username: str, password: str) -> dict:
+    user = find_user(username)
+    if not user:
+        raise AuthError("User not found")
+    if not verify_password(password, user.password_hash):
+        raise AuthError("Invalid password")
+    return create_session(user)
"""
            },
            {
                "path": "src/auth/session.py",
                "additions": 30,
                "deletions": 0,
                "patch": """
+def create_session(user: User) -> dict:
+    token = generate_token()
+    store_session(user.id, token)
+    return {"token": token, "expires": 3600}
"""
            }
        ],
        "description": "Implements user login and session management"
    }


@step(StepConfig(savepoint=True))
def analyze_code_quality(files: List[dict]) -> dict:
    """Analyze code quality issues."""
    ctx = ExecutionContext.current()
    
    print(f"Analyzing code quality for {len(files)} files...")
    
    issues = []
    
    for file in files:
        # Simulate code analysis
        if "password" in file["patch"].lower():
            issues.append({
                "file": file["path"],
                "type": "security",
                "severity": "high",
                "message": "Ensure password handling follows security best practices",
                "line": 5
            })
        
        if file["additions"] > 40:
            issues.append({
                "file": file["path"],
                "type": "complexity",
                "severity": "medium",
                "message": "Large file change - consider breaking into smaller commits",
                "line": None
            })
    
    ctx.create_savepoint({
        "goal_summary": "Code quality analysis",
        "hypotheses": ["Code follows best practices", "No critical issues"],
        "questions": ["Are there hidden security issues?"],
        "decisions": [f"Found {len(issues)} potential issues"],
        "next_step": "security_analysis"
    })
    
    return {
        "issues": issues,
        "files_analyzed": len(files),
        "quality_score": max(0, 100 - len(issues) * 10)
    }


@step(StepConfig(savepoint=True))
def analyze_security(files: List[dict]) -> dict:
    """Analyze security vulnerabilities."""
    ctx = ExecutionContext.current()
    
    print("Performing security analysis...")
    
    vulnerabilities = []
    
    for file in files:
        patch = file["patch"].lower()
        
        # Check for common security issues
        if "password" in patch and "hash" not in patch:
            vulnerabilities.append({
                "file": file["path"],
                "type": "credential_handling",
                "severity": "critical",
                "message": "Password should be hashed before storage"
            })
        
        if "token" in patch and "expire" not in patch:
            vulnerabilities.append({
                "file": file["path"],
                "type": "session_management",
                "severity": "high",
                "message": "Tokens should have expiration"
            })
    
    ctx.create_savepoint({
        "goal_summary": "Security vulnerability analysis",
        "hypotheses": ["Authentication implementation is secure"],
        "questions": ["Are there injection vulnerabilities?", "Is session handling secure?"],
        "decisions": [f"Found {len(vulnerabilities)} security concerns"],
        "next_step": "test_coverage_analysis"
    })
    
    return {
        "vulnerabilities": vulnerabilities,
        "security_score": max(0, 100 - len(vulnerabilities) * 20)
    }


@step()
def analyze_test_coverage(pr: dict) -> dict:
    """Analyze test coverage for changed files."""
    print("Analyzing test coverage...")
    
    # Simulate test coverage analysis
    coverage = []
    for file in pr["files_changed"]:
        test_file = file["path"].replace("src/", "tests/test_")
        coverage.append({
            "file": file["path"],
            "test_file": test_file,
            "has_tests": "auth" in file["path"],  # Simulated
            "coverage_percent": 75 if "auth" in file["path"] else 0
        })
    
    avg_coverage = sum(c["coverage_percent"] for c in coverage) / len(coverage) if coverage else 0
    
    return {
        "coverage": coverage,
        "average_coverage": avg_coverage,
        "files_without_tests": [c["file"] for c in coverage if not c["has_tests"]]
    }


@step()
def generate_review_comments(
    quality: dict,
    security: dict,
    coverage: dict
) -> dict:
    """Generate review comments based on analysis."""
    print("Generating review comments...")
    
    comments = []
    
    # Quality comments
    for issue in quality["issues"]:
        comments.append({
            "file": issue["file"],
            "line": issue.get("line"),
            "body": f"[{issue['severity'].upper()}] {issue['message']}",
            "category": "quality"
        })
    
    # Security comments
    for vuln in security["vulnerabilities"]:
        comments.append({
            "file": vuln["file"],
            "line": None,
            "body": f"🔒 SECURITY [{vuln['severity'].upper()}]: {vuln['message']}",
            "category": "security"
        })
    
    # Coverage comments
    for file in coverage["files_without_tests"]:
        comments.append({
            "file": file,
            "line": None,
            "body": "⚠️ This file has no test coverage. Please add tests.",
            "category": "testing"
        })
    
    return {"comments": comments}


@step()
def create_review_summary(
    pr: dict,
    quality: dict,
    security: dict,
    coverage: dict,
    comments: dict
) -> dict:
    """Create overall review summary."""
    print("Creating review summary...")
    
    # Calculate overall score
    overall_score = (
        quality["quality_score"] * 0.3 +
        security["security_score"] * 0.5 +
        coverage["average_coverage"] * 0.2
    )
    
    # Determine recommendation
    if security["security_score"] < 50:
        recommendation = "request_changes"
        summary = "🔴 Changes requested due to security concerns"
    elif overall_score < 60:
        recommendation = "request_changes"
        summary = "🟡 Changes requested - please address the issues"
    elif overall_score < 80:
        recommendation = "comment"
        summary = "🟡 Approved with suggestions"
    else:
        recommendation = "approve"
        summary = "🟢 Looks good!"
    
    return {
        "pr_id": pr["pr_id"],
        "recommendation": recommendation,
        "summary": summary,
        "overall_score": overall_score,
        "scores": {
            "quality": quality["quality_score"],
            "security": security["security_score"],
            "coverage": coverage["average_coverage"]
        },
        "total_comments": len(comments["comments"]),
        "reviewed_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@workflow()
def code_review_agent(pr_url: str) -> dict:
    """
    Automated code review workflow:
    1. Fetch pull request
    2. Analyze code quality
    3. Analyze security
    4. Check test coverage
    5. Generate comments
    6. Create summary
    
    Savepoints capture analysis state for debugging
    and allow resuming if the review is interrupted.
    """
    # Fetch PR
    pr = fetch_pull_request(pr_url)
    
    # Analyze
    quality = analyze_code_quality(pr["files_changed"])
    security = analyze_security(pr["files_changed"])
    coverage = analyze_test_coverage(pr)
    
    # Generate output
    comments = generate_review_comments(quality, security, coverage)
    summary = create_review_summary(pr, quality, security, coverage, comments)
    
    return {
        "status": "completed",
        "review": summary,
        "comments": comments["comments"]
    }


if __name__ == "__main__":
    result = code_review_agent("https://github.com/org/repo/pull/123")
    
    print(f"\nCode Review Complete!")
    print(f"PR: {result['review']['pr_id']}")
    print(f"Recommendation: {result['review']['recommendation']}")
    print(f"Summary: {result['review']['summary']}")
    print(f"\nScores:")
    for category, score in result['review']['scores'].items():
        print(f"  {category}: {score:.0f}/100")
    print(f"\nComments ({len(result['comments'])}):")
    for comment in result['comments'][:3]:
        print(f"  • {comment['body'][:60]}...")
