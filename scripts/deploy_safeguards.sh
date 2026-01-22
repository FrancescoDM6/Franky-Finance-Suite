#!/bin/bash
set -eo pipefail

echo "==================================================="
echo "   Phinan Finance Suite - Safeguards Deployment"
echo "==================================================="

# ---------------------------------------------------------
# 1. Environment Discovery (Metadata Server)
# ---------------------------------------------------------
echo "[1/4] Detecting GCP environment..."

if ! command -v gcloud &> /dev/null; then
    echo "Error: 'gcloud' CLI not found. Is this running on a GCP VM?"
    exit 1
fi

# Fetch Project ID
PROJECT_ID=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/project/project-id)
# Fetch Zone (format: projects/123/zones/us-central1-a -> us-central1-a)
ZONE_FULL=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone)
ZONE=${ZONE_FULL##*/}
# Fetch Instance Name
INSTANCE_NAME=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
# Fetch Service Account email
SERVICE_ACCOUNT=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email)

echo "  -> Project:  $PROJECT_ID"
echo "  -> Zone:     $ZONE"
echo "  -> VM Name:  $INSTANCE_NAME"
echo "  -> Service Account: $SERVICE_ACCOUNT"
echo ""

# ---------------------------------------------------------
# 2. Configure Cloud Function
# ---------------------------------------------------------
echo "[2/4] Deploying Auto-Shutdown Cloud Function..."
echo "       (This may take 2-3 minutes)"

# Ensure Pub/Sub topic exists
if ! gcloud pubsub topics describe budget-alerts --project="$PROJECT_ID" &> /dev/null; then
    echo "  -> Creating Pub/Sub topic 'budget-alerts'..."
    gcloud pubsub topics create budget-alerts --project="$PROJECT_ID"
else
    echo "  -> Pub/Sub topic 'budget-alerts' already exists."
fi

# Deploy Function
# We need to be in the root, so point to cloud_function dir
gcloud functions deploy stop-vm-on-budget \
    --gen2 \
    --runtime=python311 \
    --region="${ZONE%-*}" \
    --source=./cloud_function \
    --entry-point=stop_vm_on_budget \
    --trigger-topic=budget-alerts \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_ZONE=$ZONE,GCP_INSTANCE_NAME=$INSTANCE_NAME" \
    --project="$PROJECT_ID" \
    --quiet

echo "  -> Cloud Function deployed successfully."

# ---------------------------------------------------------
# 3. Permissions
# ---------------------------------------------------------
echo "[3/4] Verifying IAM Permissions..."
echo "       Ensuring the Cloud Function has permission to stop this VM."

# Get the identity of the Cloud Function (it might be the default compute account or a specific one)
# For Gen2, it defaults to the compute service account usually, but let's check.
FUNCTION_SA=$(gcloud functions describe stop-vm-on-budget --region="${ZONE%-*}" --gen2 --format="value(serviceConfig.serviceAccountEmail)" --project="$PROJECT_ID")

echo "  -> Function is running as: $FUNCTION_SA"

# Grant instanceAdmin to this SA on the project
# Note: This might fail if the VM's implementation of gcloud doesn't have IAM writing rights.
# We will try, but warn if it fails.

set +e # Disable exit on error for this step
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$FUNCTION_SA" \
    --role="roles/compute.instanceAdmin.v1" \
    --condition=None \
    --quiet &> /dev/null

if [ $? -eq 0 ]; then
    echo "  -> Permission 'compute.instanceAdmin.v1' granted successfully."
else
    echo ""
    echo "  [WARNING] Could not automatically grant permissions."
    echo "  The VM's service account ($SERVICE_ACCOUNT) might lack 'Project IAM Admin' rights."
    echo "  PLEASE RUN THIS MANUALLY IN GCLOUD CONSOLE (Cloud Shell):"
    echo "  ---------------------------------------------------------"
    echo "  gcloud projects add-iam-policy-binding $PROJECT_ID \\"
    echo "    --member='serviceAccount:$FUNCTION_SA' \\"
    echo "    --role='roles/compute.instanceAdmin.v1'"
    echo "  ---------------------------------------------------------"
    echo ""
fi
set -e

# ---------------------------------------------------------
# 4. Success
# ---------------------------------------------------------
echo "==================================================="
echo "Safeguards Deployed!"
echo "==================================================="
echo "Next Steps:"
echo "1. Go to GCP Console -> Billing -> Budgets & Alerts"
echo "2. Create a budget (e.g., \$25)"
echo "3. Connect it to Pub/Sub topic: projects/$PROJECT_ID/topics/budget-alerts"
echo "4. Tick 'Email alerts' just in case."
echo "==================================================="
