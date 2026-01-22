"""
Cloud Function to stop a GCP VM instance when budget threshold is exceeded.

Triggered by Pub/Sub message from GCP Budget Alerts.
"""

import os
import logging
from google.cloud import compute_v1

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - override via environment variables
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-project-id")
ZONE = os.environ.get("GCP_ZONE", "us-central1-a")
INSTANCE_NAME = os.environ.get("GCP_INSTANCE_NAME", "phinan-vm")


def stop_vm_on_budget(event, context):
    """
    Triggered by Pub/Sub when budget threshold is hit.
    
    Args:
        event (dict): The Pub/Sub event payload
        context (google.cloud.functions.Context): Metadata for the event
    """
    try:
        logger.info(f"Budget alert received. Stopping VM {INSTANCE_NAME} in {ZONE}")
        
        # Initialize Compute Engine client
        client = compute_v1.InstancesClient()
        
        # Stop the instance
        operation = client.stop(
            project=PROJECT_ID,
            zone=ZONE,
            instance=INSTANCE_NAME
        )
        
        logger.info(f"Stop operation initiated: {operation.name}")
        logger.info(f"VM {INSTANCE_NAME} has been stopped due to budget alert")
        
        return {"status": "success", "message": f"VM {INSTANCE_NAME} stopped"}
        
    except Exception as e:
        logger.error(f"Failed to stop VM: {str(e)}")
        raise
