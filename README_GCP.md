# GCP Deployment Guide (Compute Engine)

This file is a standalone, step-by-step guide to deploy this project on GCP so other users can access it at:

`https://debate.agent.com`

It uses:
- Compute Engine VM
- Cloud DNS
- Docker Compose stack from this repo (`docker-compose.cloud.yml`)
- Caddy for automatic HTTPS certificates

## 0. What You Need First

1. A GCP account with billing enabled.
2. A registered domain where you can change nameservers (for this guide: `agent.com`).
3. A Tavily API key.
4. `gcloud` CLI installed on your local machine.

## 1. Set Deployment Variables (Local Machine)

Why: These variables prevent copy/paste mistakes and keep commands consistent.

Run:

```bash
export PROJECT_ID="gen-lang-client-0560346528"
export REGION="asia-south1"
export ZONE="asia-south1-a"
export VM_NAME="debate-app-vm"
export MACHINE_TYPE="e2-standard-4"
export DISK_SIZE_GB="120"
export ADDRESS_NAME="debate-app-ip"
export TAG_NAME="debate-app"
export DNS_ZONE_NAME="debate-zone"
export ROOT_DOMAIN="agent.com"
export APP_DOMAIN="debate.agent.com"
```

## 2. Authenticate With GCP

Why: Grants your local `gcloud` session permission to create resources.

```bash
gcloud auth login
gcloud config set project "$PROJECT_ID"
```

Success check:

```bash
gcloud config get-value project
```

## 3. Enable Required APIs

Why: GCP services are disabled by default in new projects.

```bash
gcloud services enable compute.googleapis.com dns.googleapis.com
```

## 4. Reserve a Static Public IP

Why: Your domain must point to a stable IP that does not change on reboot.

```bash
gcloud compute addresses create "$ADDRESS_NAME" --region "$REGION"
export PUBLIC_IP=$(gcloud compute addresses describe "$ADDRESS_NAME" --region "$REGION" --format='value(address)')
echo "$PUBLIC_IP"
```

## 5. Create the VM

Why: This machine will run backend/frontend/postgres/redis/ollama/caddy.

```bash
gcloud compute instances create "$VM_NAME" \
  --zone "$ZONE" \
  --machine-type "$MACHINE_TYPE" \
  --boot-disk-size "${DISK_SIZE_GB}GB" \
  --boot-disk-type "pd-ssd" \
  --image-family "ubuntu-2204-lts" \
  --image-project "ubuntu-os-cloud" \
  --address "$PUBLIC_IP" \
  --tags "$TAG_NAME"
```

## 6. Open Firewall Ports

Why: HTTPS traffic (80/443) and SSH (22) must be allowed.

```bash
gcloud compute firewall-rules create "${TAG_NAME}-web" \
  --allow tcp:80,tcp:443 \
  --target-tags "$TAG_NAME" \
  --description "Public HTTPS for debate app"

gcloud compute firewall-rules create "${TAG_NAME}-ssh" \
  --allow tcp:22 \
  --target-tags "$TAG_NAME" \
  --description "SSH access for deployment"
```

## 7. Configure Cloud DNS

Why: Lets users access your app by domain name instead of IP.

Create zone:

```bash
gcloud dns managed-zones create "$DNS_ZONE_NAME" \
  --dns-name "${ROOT_DOMAIN}." \
  --description "DNS zone for debate app"

gcloud dns managed-zones describe "$DNS_ZONE_NAME" --format='value(nameServers)'
```

Action required: Copy the nameservers shown above and set them at your domain registrar for `agent.com`.

Create app record:

```bash
gcloud dns record-sets create "${APP_DOMAIN}." \
  --type "A" \
  --ttl "300" \
  --zone "$DNS_ZONE_NAME" \
  --rrdatas "$PUBLIC_IP"

dig +short "$APP_DOMAIN"
```

`dig` should return your `PUBLIC_IP`.

## 8. SSH Into the VM

```bash
gcloud compute ssh "$VM_NAME" --zone "$ZONE"
```

## 9. Install Docker + Compose (On VM)

Why: The project ships as Docker Compose services.

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 10. Clone Repo and Prepare Cloud Env (On VM)

```bash
git clone https://github.com/BHUVI-SHIP-IT/multi-agent-debate-system.git
cd multi-agent-debate-system
cp .env.cloud.example .env.cloud
```

Edit `.env.cloud`:

```env
PUBLIC_DOMAIN=debate.agent.com
LETSENCRYPT_EMAIL=lolm06855@gmail.com
TAVILY_API_KEY=your_real_tavily_key
OLLAMA_MODEL=llama3.2
POSTGRES_USER=debate
POSTGRES_PASSWORD=use_a_strong_password_here
POSTGRES_DB=debate_db
CORS_ORIGINS=https://debate.agent.com
```

## 11. Build and Start the Full Stack (On VM)

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml up -d --build
```

## 12. Pull Ollama Model (On VM)

Why: Backend cannot answer until model is available in Ollama.

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml exec ollama ollama pull llama3.2
```

## 13. Verify Deployment (On VM)

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml ps
docker compose --env-file .env.cloud -f docker-compose.cloud.yml logs caddy --tail=100
```

Open in browser:

`https://debate.agent.com`

## 14. Updates and Operations (On VM)

Update app:

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml up -d --build
```

Stop app:

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml down
```

View logs:

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml logs -f
```

## Common Issues

0. `FAILED_PRECONDITION: Billing account for project ... is not open` when enabling APIs.
- Cause: active project has no linked billing account, or billing account is closed.
- Fix:

```bash
# Check active project
gcloud config get-value project

# (Optional) force the intended project from this guide
gcloud config set project "gen-lang-client-0560346528"

# Check billing link status
gcloud beta billing projects describe "$(gcloud config get-value project)"

# List billing accounts you can use
gcloud beta billing accounts list

# Link project to an OPEN billing account (replace ID)
gcloud beta billing projects link "$(gcloud config get-value project)" \
  --billing-account="000000-000000-000000"

# Retry API enable
gcloud services enable compute.googleapis.com dns.googleapis.com
```

If `billing accounts list` is empty or link fails with permissions, ask your GCP org/project owner to grant billing permissions (Billing Account User + Project Billing Manager/Owner).

1. Domain opens on HTTP but not HTTPS.
- Cause: DNS not propagated or port 443 blocked.
- Fix: verify `dig +short debate.agent.com` and firewall rules.

2. Caddy cannot issue cert.
- Cause: domain does not resolve to VM public IP.
- Fix: fix DNS A record and wait propagation.

3. Backend errors connecting to DB.
- Cause: wrong `POSTGRES_*` in `.env.cloud`.
- Fix: update values and restart compose stack.

4. First response is slow.
- Cause: model cold start in Ollama.
- Fix: warm up model once after deploy.
