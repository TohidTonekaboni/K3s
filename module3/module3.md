# Module 3 — Networking

Commands and manifests for each exercise in Module 3 of [../roadmap.md](../roadmap.md).

## 1. Two apps talking via Kubernetes DNS

Create `api-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: hashicorp/http-echo
          args: ["-text=hello from api"]
          ports:
            - containerPort: 5678
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 5678
```

Create `frontend-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: frontend
          image: busybox
          command: ["sleep", "3600"]
```

```bash
kubectl apply -f api-deployment.yaml
kubectl apply -f frontend-deployment.yaml

# call the api from the frontend pod using k8s DNS
kubectl exec deploy/frontend -- wget -qO- api.default.svc.cluster.local
kubectl exec deploy/frontend -- wget -qO- api   # short name works within same namespace
```

## 2. DNS resolution with a debug pod

```bash
kubectl run tmp --rm -it --image=busybox --restart=Never -- sh
# inside the shell:
nslookup api
nslookup api.default.svc.cluster.local
nslookup kubernetes.default
exit
```

## 3. Ingress via Traefik (k3s default)

Create `ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: apps-ingress
spec:
  rules:
    - http:
        paths:
          - path: /app1
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
          - path: /app2
            pathType: Prefix
            backend:
              service:
                name: frontend-svc
                port:
                  number: 80
```

For `/app2` to work you need a Service in front of the frontend deployment
too — reuse the pattern from `api`'s Service, pointing `selector: app:
frontend` at port 80. Apply everything and test:

```bash
kubectl apply -f ingress.yaml
kubectl get ingress apps-ingress

# k3s's Traefik listens on the node at :80 by default
curl http://localhost/app1
curl http://localhost/app2
```

If `localhost` doesn't route (depends on your k3d/VM port mapping), find the
node IP or the port k3d mapped to the Traefik service:

```bash
kubectl get nodes -o wide
kubectl get svc -n kube-system traefik
```

## 4. LoadBalancer vs NodePort

```bash
kubectl expose deployment api --name=api-lb --port=80 --target-port=5678 --type=LoadBalancer
kubectl get svc api-lb
# k3s's ServiceLB (Klipper) should assign an EXTERNAL-IP automatically
curl http://<external-ip>:80

kubectl expose deployment api --name=api-nodeport --port=80 --target-port=5678 --type=NodePort
kubectl get svc api-nodeport
curl http://<node-ip>:<node-port>
```

Compare: NodePort exposes a high port (30000-32767) on every node;
LoadBalancer (via ServiceLB in k3s) gives you a stable IP on port 80 without
picking a random port yourself — but on a bare k3d/Docker setup, both
ultimately route through the same node network.

## 5. NetworkPolicy across namespaces

```bash
kubectl create namespace team-a
kubectl create namespace team-b

kubectl run app --image=busybox --command --restart=Never -n team-a -- sleep 3600
kubectl run app --image=busybox --command --restart=Never -n team-b -- sleep 3600
kubectl expose pod app -n team-a --port=80 --target-port=80 --name=app
```

Create `netpol-deny-cross-namespace.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-from-other-namespaces
  namespace: team-a
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector: {}
```

This only allows ingress from pods within `team-a` itself (empty
`podSelector` under `from` matches all pods in the same namespace), blocking
everything else, including `team-b`.

```bash
kubectl apply -f netpol-deny-cross-namespace.yaml

# before applying, this would succeed; after, it should fail/timeout
kubectl exec -n team-b app -- wget -qO- --timeout=5 app.team-a.svc.cluster.local
```

k3s's default CNI is Flannel, which does **not** enforce NetworkPolicy on
its own — if the test above doesn't actually block traffic, that's why.
To see enforcement work, install a NetworkPolicy-capable CNI (e.g. Calico)
or enable k3s with `--flannel-backend=none` plus a policy-aware CNI.

## Cleanup when done with the module

```bash
kubectl delete -f api-deployment.yaml -f frontend-deployment.yaml -f ingress.yaml
kubectl delete svc api-lb api-nodeport
kubectl delete namespace team-a team-b
```
</content>
</invoke>
