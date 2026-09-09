#!/bin/bash
# ====================================================================
# Automated AWS ECR & Deployment Script for KPI Intelligence Reporter
# ====================================================================

set -e

REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"
REPO_NAME="kpi-intelligence-reporter"

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "❌ Error: AWS_ACCOUNT_ID environment variable is not set."
    echo "Usage: AWS_ACCOUNT_ID=123456789012 AWS_REGION=us-east-1 ./aws/deploy.sh"
    exit 1
fi

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"

echo "🚀 Step 1: Authenticating Docker with AWS ECR (${REGION})..."
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "📦 Step 2: Ensuring ECR Repository exists..."
aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${REGION}" 2>/dev/null || \
aws ecr create-repository --repository-name "${REPO_NAME}" --region "${REGION}"

echo "🔨 Step 3: Building Docker Image..."
docker build -t "${REPO_NAME}:latest" .

echo "🏷️ Step 4: Tagging Image for AWS ECR..."
docker tag "${REPO_NAME}:latest" "${ECR_URI}:latest"

echo "⬆️ Step 5: Pushing Docker Image to AWS ECR..."
docker push "${ECR_URI}:latest"

echo "✅ AWS ECR Push Successful!"
echo "Image URI: ${ECR_URI}:latest"
echo "You can now select this image in AWS App Runner or AWS ECS Fargate."
