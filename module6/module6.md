# Module 6 — Packaging & GitOps-lite

Commands and manifests for each exercise in Module 6 of [../roadmap.md](../roadmap.md).

## 1. Install Helm and deploy a public chart

```bash
brew install helm   # or see https://helm.sh/docs/intro/install/

helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install my-redis bitnami/redis
kubectl get pods -l app.kubernetes.io/instance=my-redis

helm get manifest my-redis | less   # see every resource the chart actually rendered
helm get values my-redis            # see the values it was installed with
```

```bash
helm uninstall my-redis
```

## 2. Your own minimal Helm chart

`my-chart/` packages the Module 3 `api` app (an `http-echo` deployment +
service) with `values.yaml` controlling the image tag, replica count, and
response text:

```yaml
# my-chart/Chart.yaml
apiVersion: v2
name: my-chart
description: Minimal Helm chart for the Module 3 api app
type: application
version: 0.1.0
appVersion: "1.0"
```

```yaml
# my-chart/values.yaml
image:
  repository: hashicorp/http-echo
  tag: latest

replicaCount: 1

text: "hello from helm"
```

Templates reference these values with `{{ .Values.* }}`:

```yaml
# my-chart/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-api
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}-api
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-api
    spec:
      containers:
        - name: api
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          args: ["-text={{ .Values.text }}"]
          ports:
            - containerPort: 5678
```

```bash
# render locally without installing, to sanity-check the templates
helm template demo my-chart/

# install with defaults
helm install demo my-chart/
kubectl get deploy,svc -l app=demo-api

# override values at install time
helm upgrade demo my-chart/ --set replicaCount=3 --set text="hello v2"
kubectl get pods -l app=demo-api

helm uninstall demo
```

## 3. Kustomize base + dev/prod overlays

`kustomize/base/` holds the shared `Deployment` + `Service`:

```yaml
# kustomize/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
```

Each overlay reuses the base and patches only what differs — replica count
and the response text — via a `namePrefix` and a JSON patch, with no
duplicated YAML:

```yaml
# kustomize/overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namePrefix: dev-
resources:
  - ../../base
patches:
  - target:
      kind: Deployment
      name: api
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
      - op: replace
        path: /spec/template/spec/containers/0/args
        value: ["-text=hello from dev"]
```

`kustomize/overlays/prod/kustomization.yaml` follows the same shape with
`replicas: 3` and `"-text=hello from prod"`.

```bash
kubectl kustomize kustomize/overlays/dev    # preview the rendered dev manifests
kubectl apply -k kustomize/overlays/dev
kubectl apply -k kustomize/overlays/prod

kubectl get deploy dev-api prod-api
kubectl get pods -l app=api    # dev-* pods (1 replica) vs prod-* pods (3 replicas)
```

Compare: Helm uses a templating language and versioned releases
(`helm upgrade`/`rollback`/`history`); Kustomize is plain YAML + patches with
no templating and no release history — `kubectl apply -k` is idempotent but
there's no built-in rollback beyond re-applying an older overlay from git.

## 4. (Optional) GitOps loop with Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

kubectl port-forward svc/argocd-server -n argocd 8080:443
# UI at https://localhost:8080, initial admin password:
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```

Point an Argo CD `Application` at a git repo path containing
`kustomize/overlays/dev` (or this repo itself), then push a change to that
overlay and watch Argo CD auto-sync it into the cluster — no manual
`kubectl apply` needed once it's wired up.

```bash
kubectl delete namespace argocd
```

## Cleanup when done with the module

```bash
helm uninstall demo my-redis 2>/dev/null
kubectl delete -k kustomize/overlays/dev
kubectl delete -k kustomize/overlays/prod
```
