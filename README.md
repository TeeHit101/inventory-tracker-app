# inventory-tracker-app

A containerized web app deployed on Kubernetes using GitOps

---

Features:
- Containerized application ( Docker )
- Kubernetes ready
- Integrated with GitOps deployment

---

Stacks:
- Docker
- Kuberntes
- Github
- GitOps (FluxCD)

---

Deployment:
- Application code is updated in this repo
- Container image is built (via CI/CD)
- Kubernetes manifests are updated in inventory-tracker-config
- FluxCD dectects change and deploys automatically to AWS EKS

---

This app deploy through: 
- infrastructure https://github.com/TeeHit101/EKS-OPENTOFU-DEMO
- GitOps configuration: https://github.com/TeeHit101/inventory-tracker-config

--- 

Outcome: 
- built as a container
- deployed to Kubernetes
- Managed via GitOps
- Integrated into a full DevOps pipeline
