# GCP Budget Auto-Shutdown Cloud Function

This Cloud Function automatically stops your GCP VM instance when a budget threshold is exceeded, preventing unexpected costs.

## Prerequisites

1. A GCP project with billing enabled
2. A Compute Engine VM instance running Phinan Finance Suite
3. `gcloud` CLI installed and authenticated

## Setup Instructions

### 1. Create a Budget with Pub/Sub Alert

```bash
# Create a Pub/Sub topic for budget alerts
gcloud pubsub topics create budget-alerts

# Create a budget in GCP Console:
# Go to: Billing → Budgets & alerts → CREATE BUDGET
# 
# Budget settings:
# - Name: phinan-monthly-budget
# - Amount: $25 (or your preferred limit)
# - Alert threshold: 100%
# - Connect to Pub/Sub topic: budget-alerts
```

### 2. Deploy the Cloud Function

```bash
# Navigate to this directory
cd cloud_function

# Deploy the function
gcloud functions deploy stop-vm-on-budget \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=stop_vm_on_budget \
  --trigger-topic=budget-alerts \
  --set-env-vars=GCP_PROJECT_ID=your-project-id,GCP_ZONE=us-central1-a,GCP_INSTANCE_NAME=phinan-vm
```

**Important**: Replace the following values:
- `your-project-id`: Your GCP project ID
- `us-central1-a`: Your VM's zone
- `phinan-vm`: Your VM's instance name

### 3. Grant Permissions

The Cloud Function needs permission to stop VM instances:

```bash
# Get the service account email
gcloud functions describe stop-vm-on-budget --region=us-central1 --gen2 --format="value(serviceConfig.serviceAccountEmail)"

# Grant compute.instanceAdmin.v1 role
gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/compute.instanceAdmin.v1"
```

Replace `SERVICE_ACCOUNT_EMAIL` with the email from the first command.

### 4. Test the Function

```bash
# Manually trigger the function to verify it works
gcloud pubsub topics publish budget-alerts --message='{"test": true}'

# Check if your VM stopped
gcloud compute instances describe phinan-vm --zone=us-central1-a
```

## How It Works

1. **Budget monitoring**: GCP continuously monitors your spending.
2. **Alert trigger**: When spending reaches 100% of your budget, a Pub/Sub message is published.
3. **Function execution**: The Cloud Function receives the Pub/Sub message and calls the Compute Engine API to stop your VM.
4. **VM shutdown**: Your VM is gracefully stopped, preventing further charges.

## Cost

- **Cloud Function**: Free tier includes 2M invocations/month
- **Pub/Sub**: Free tier includes 10GB messages/month
- **Total estimated cost**: $0/month (well within free tier)

## Monitoring

View function logs:

```bash
gcloud functions logs read stop-vm-on-budget --region=us-central1 --gen2 --limit=50
```

## Additional Protection Layers

This Cloud Function is one layer of protection. Consider also:

1. **Billing spending limit**: Set a hard cap in GCP Console → Billing → Account Management
2. **Email alerts**: Set budget alerts at 50%, 80%, and 100%
3. **Cloud Monitoring**: Set up alerts for high memory/CPU usage

## Resuming Your VM

If the budget threshold is reached and your VM is stopped:

```bash
# Start your VM manually
gcloud compute instances start phinan-vm --zone=us-central1-a
```

Consider reviewing your usage and adjusting your budget or instance type if this happens frequently.
