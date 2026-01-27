# Terraform Infrastructure

## Modules

### AWS (`terraform/aws`)
- VPC with public/private subnets
- EKS cluster with managed node groups
- RDS PostgreSQL with Multi-AZ support
- ElastiCache Redis cluster
- S3 bucket for snapshots

### GCP (`terraform/gcp`)
- VPC network with subnets
- GKE cluster with autoscaling
- Cloud SQL PostgreSQL
- Memorystore Redis
- Cloud Storage bucket

### Azure (`terraform/azure`)
- Virtual Network
- AKS cluster
- PostgreSQL Flexible Server
- Azure Cache for Redis
- Storage Account with blob containers

## Usage

```bash
cd terraform/aws  # or gcp, azure

# Initialize
terraform init

# Plan
terraform plan -var="environment=dev"

# Apply
terraform apply -var="environment=dev"
```

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| project_name | Project identifier | contd |
| environment | Environment name | dev |
| *_region | Cloud region | varies |
