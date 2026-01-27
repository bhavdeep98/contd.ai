# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please
report it responsibly.

### How to Report

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email security@contd.ai with details
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 1 week
- **Resolution Timeline**: Depends on severity
  - Critical: 24-72 hours
  - High: 1-2 weeks
  - Medium: 2-4 weeks
  - Low: Next release cycle

### Disclosure Policy

- We follow coordinated disclosure
- We'll credit reporters (unless anonymity is requested)
- We'll notify you before public disclosure

## Security Best Practices

When using Contd:

1. **API Keys**: Never commit API keys or secrets
2. **Database**: Use strong passwords and encryption at rest
3. **Network**: Use TLS for all connections
4. **Updates**: Keep Contd and dependencies updated
5. **Access Control**: Use least-privilege principles

## Security Features

Contd includes:
- API key authentication
- Rate limiting
- Input validation
- Audit logging
- Encrypted state storage (optional)
