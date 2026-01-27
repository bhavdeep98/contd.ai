# Helm Charts

## Installation

```bash
# Add dependencies
helm dependency update helm/contd

# Install (dev)
helm install contd helm/contd -f helm/contd/values-dev.yaml

# Install (production with external databases)
helm install contd helm/contd \
  -f helm/contd/values-production.yaml \
  --set contd.database.host=mydb.example.com \
  --set contd.redis.host=myredis.example.com
```

## Upgrade

```bash
helm upgrade contd helm/contd -f helm/contd/values-production.yaml
```

## Uninstall

```bash
helm uninstall contd
```

## Values Files

- `values.yaml` - Default values
- `values-dev.yaml` - Development environment
- `values-staging.yaml` - Staging environment
- `values-production.yaml` - Production environment
