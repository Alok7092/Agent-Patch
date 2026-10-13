# Azure App Service Deployment

## Prerequisites
- Azure CLI installed and logged in
- Resource group created
- Azure Container Registry (ACR) or Docker Hub

## Steps

### 1. Build and push image
```bash
docker build -t snap -f deploy/Dockerfile .
docker tag snap <acr-name>.azurecr.io/snap:latest
docker push <acr-name>.azurecr.io/snap:latest
```

### 2. Create App Service
```bash
az webapp create \
  --resource-group <rg-name> \
  --plan <plan-name> \
  --name snap \
  --deployment-container-image-name <acr-name>.azurecr.io/snap:latest
```

### 3. Configure environment
```bash
az webapp config appsettings set --name snap --resource-group <rg-name> --settings \
  AGENT_PATCH_MODE=azure \
  AZURE_TENANT_ID=<tenant-id> \
  AZURE_CLIENT_ID=<client-id> \
  AZURE_CLIENT_SECRET=<secret> \
  AWS_ACCESS_KEY_ID=<key> \
  AWS_SECRET_ACCESS_KEY=<secret> \
  AWS_REGION=us-east-1
```

### 4. Mount persistent storage
```bash
az webapp config storage-account add \
  --name snap \
  --resource-group <rg-name> \
  --custom-id data \
  --storage-type AzureFiles \
  --share-name snap-data \
  --mount-path /app/data
```
