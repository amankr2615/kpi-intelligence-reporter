# ☁️ AWS Production Deployment Guide — KPI Intelligence Reporter

This guide details how to deploy the **KPI Intelligence Reporter** to **AWS App Runner** and **AWS ECS Fargate** with zero hardcoded keys, VPC isolation, and automated container health checks.

---

## 🛠️ Prerequisites

1. **AWS CLI** installed and configured (`aws configure`).
2. **Docker** installed and running locally.
3. An active AWS Account with permissions for ECR, App Runner, ECS, and Secrets Manager.

---

## 🚀 Step 1: Push Container to AWS ECR

Run the automated deployment script:

```bash
AWS_ACCOUNT_ID="123456789012" AWS_REGION="us-east-1" ./aws/deploy.sh
```

This script will:
1. Authenticate Docker with AWS ECR.
2. Create the `kpi-intelligence-reporter` ECR repository if it doesn't exist.
3. Build the container from `Dockerfile`.
4. Tag and push `kpi-intelligence-reporter:latest` to AWS ECR.

---

## 🔒 Step 2: Store Secrets in AWS Secrets Manager

Create your application secrets in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
    --name "kpi/gemini_key" \
    --secret-string "YOUR_GEMINI_API_KEY" \
    --region us-east-1

aws secretsmanager create-secret \
    --name "kpi/supabase_url" \
    --secret-string "https://your-project.supabase.co" \
    --region us-east-1

aws secretsmanager create-secret \
    --name "kpi/supabase_key" \
    --secret-string "YOUR_SUPABASE_KEY" \
    --region us-east-1
```

---

## ⚡ Option A: Deploy to AWS App Runner (Fastest & Managed)

1. Open the **AWS App Runner Console**.
2. Click **Create an App Runner service**.
3. Source: Select **Container Registry** ➔ **Amazon ECR**.
4. Image URI: Select `kpi-intelligence-reporter:latest`.
5. Under **Deployment settings**, choose **Automatic** (deploys new images automatically when pushed).
6. Under **Environment variables**, map:
   * `PORT`: `8000`
   * `GEMINI_API_KEY`: Reference AWS Secrets Manager ARN.
   * `SUPABASE_URL`: Reference AWS Secrets Manager ARN.
   * `SUPABASE_KEY`: Reference AWS Secrets Manager ARN.
7. Health Check: Path `/health`, Port `8000`.
8. Click **Create & Deploy**.

---

## 🏛️ Option B: Deploy to AWS ECS Fargate (Enterprise VPC Setup)

1. Register the ECS task definition:
   ```bash
   aws ecs register-task-definition --cli-input-json file://aws/ecs-task-definition.json
   ```
2. Create an ECS Cluster:
   ```bash
   aws ecs create-cluster --cluster-name kpi-reporter-cluster
   ```
3. Create an ECS Service attached to your **VPC Private Subnets** and **Application Load Balancer (ALB)**.

---

## 📊 Monitoring & Logs
* **App Runner / ECS Logs:** Streamed live to **AWS CloudWatch** under `/aws/apprunner/kpi-intelligence-reporter` or `/ecs/kpi-intelligence-reporter`.
* **Health Endpoint:** `GET /health` returns `{"status": "ok"}` for ALB/App Runner health probes.
