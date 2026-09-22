# Module 5 — Observability & Debugging

Commands and manifests for each exercise in Module 5 of [../roadmap.md](../roadmap.md).

## 1. metrics-server and `kubectl top`

k3s doesn't bundle `metrics-server` by default (k3d clusters don't either),
so install it:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

On k3d/self-signed clusters the kubelet's certs usually aren't trusted by
metrics-server, so it stays stuck without this patch:

```bash
kubectl patch deployment metrics-server -n kube-system --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

kubectl get pods -n kube-system -l k8s-app=metrics-server -w
```

Once it's `Running`:

```bash
kubectl top nodes
kubectl top pods -A
```

## 2. Diagnosing CrashLoopBackOff

Create `crashloop-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crashy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: crashy
  template:
    metadata:
      labels:
        app: crashy
    spec:
      containers:
        - name: crashy
          image: busybox
          command: ["sh", "-c", "echo booting; sleep 2; echo crashing now; exit 1"]
```

```bash
kubectl apply -f crashloop-deployment.yaml
kubectl get pods -l app=crashy -w   # watch status cycle: Running -> Error -> CrashLoopBackOff

kubectl logs -l app=crashy               # logs from the current (failing) attempt
kubectl logs -l app=crashy --previous    # logs from the last terminated attempt
kubectl describe pod -l app=crashy | grep -A10 "Last State"
# look for: Reason: Error, Exit Code: 1, and the growing restart count/backoff
```

## 3. Simulating a stuck rollout

Create `rollout-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: web
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
```

```bash
kubectl apply -f rollout-deployment.yaml
kubectl rollout status deployment/web   # confirm it's healthy first

# push a bad image tag that doesn't exist
kubectl set image deployment/web web=nginx:this-tag-does-not-exist
kubectl rollout status deployment/web --timeout=30s   # times out / stalls

kubectl get pods -l app=web             # some pods stuck in ImagePullBackOff
kubectl rollout history deployment/web
kubectl rollout undo deployment/web     # roll back to the last good revision
kubectl rollout status deployment/web   # confirm it recovers
```

## 4. Debug pod pattern

Use the `crashy` or `web` deployment from above without modifying it:

```bash
# ephemeral container attached to a running pod (needs a shell-capable image)
kubectl debug -it deploy/web --image=busybox --target=web -- sh

# or spin up a standalone debug pod on the same node for network/DNS checks
kubectl debug node/<node-name> -it --image=busybox
```

The ephemeral container shares the target pod's namespaces (network, PID
depending on flags) without touching the running container's spec or
restarting it — useful when the app image itself has no shell/tools.

## 5. Cluster-wide events

```bash
kubectl get events --sort-by=.lastTimestamp -A
```

Watch for `Warning` events (`BackOff`, `FailedScheduling`, `Unhealthy`,
`ImagePullBackOff`) correlating with the failures you triggered above — this
is often the fastest way to spot what's wrong across a whole namespace or
cluster without checking each resource individually.

## Cleanup when done with the module

```bash
kubectl delete -f crashloop-deployment.yaml -f rollout-deployment.yaml
kubectl delete -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```
