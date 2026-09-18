# Module 4 — Workload Types & Scheduling

Commands and manifests for each exercise in Module 4 of [../roadmap.md](../roadmap.md).

## 1. StatefulSet with stable naming and per-pod PVCs

Create `statefulset.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  clusterIP: None
  selector:
    app: redis
  ports:
    - port: 6379
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis
  replicas: 2
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          volumeMounts:
            - name: data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 100Mi
```

```bash
kubectl apply -f statefulset.yaml
kubectl get pods -l app=redis -w   # watch redis-0 come up, then redis-1
kubectl get pvc
```

Note the pod names are stable (`redis-0`, `redis-1`, not random suffixes) and
each has its own PVC (`data-redis-0`, `data-redis-1`) that survives pod
restarts, unlike a Deployment's shared/ephemeral storage.

## 2. DaemonSet — one pod per node

Create `daemonset.yaml`:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-agent
spec:
  selector:
    matchLabels:
      app: node-agent
  template:
    metadata:
      labels:
        app: node-agent
    spec:
      containers:
        - name: node-agent
          image: busybox
          command: ["sleep", "3600"]
```

```bash
kubectl apply -f daemonset.yaml
kubectl get nodes
kubectl get pods -o wide -l app=node-agent
```

You should see exactly one `node-agent` pod per node, each pinned to a
different `NODE` in the `-o wide` output.

## 3. Job and CronJob

Create `job.yaml`:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: one-off-task
spec:
  template:
    spec:
      containers:
        - name: task
          image: busybox
          command: ["sh", "-c", "echo doing work; sleep 5; echo done"]
      restartPolicy: Never
  backoffLimit: 2
```

Create `cronjob.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: minute-job
spec:
  schedule: "* * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: task
              image: busybox
              command: ["sh", "-c", "date; echo tick"]
          restartPolicy: OnFailure
```

```bash
kubectl apply -f job.yaml
kubectl get jobs
kubectl logs job/one-off-task

kubectl apply -f cronjob.yaml
kubectl get jobs,cronjobs -w   # watch a new job spawn every minute
```

## 4. Resource requests/limits and OOMKilled

Create `resource-limits-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memory-hog
spec:
  replicas: 1
  selector:
    matchLabels:
      app: memory-hog
  template:
    metadata:
      labels:
        app: memory-hog
    spec:
      containers:
        - name: memory-hog
          image: polinux/stress
          command: ["stress"]
          args: ["--vm", "1", "--vm-bytes", "150M", "--vm-hang", "1"]
          resources:
            requests:
              cpu: "50m"
              memory: "50Mi"
            limits:
              cpu: "200m"
              memory: "50Mi"
```

The container tries to allocate 150Mi but the memory limit is set to 50Mi,
so the kernel OOM-killer should kill it almost immediately.

```bash
kubectl apply -f resource-limits-deployment.yaml
kubectl get pods -l app=memory-hog -w
kubectl describe pod -l app=memory-hog | grep -A5 "Last State"
# look for: Reason: OOMKilled
```

## 5. Pinning a pod with nodeSelector

Label a node, then create `node-affinity-pod.yaml`:

```bash
kubectl get nodes
kubectl label node <node-name> disktype=fast
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: pinned-pod
spec:
  nodeSelector:
    disktype: fast
  containers:
    - name: pinned
      image: busybox
      command: ["sleep", "3600"]
```

```bash
kubectl apply -f node-affinity-pod.yaml
kubectl get pod pinned-pod -o wide   # NODE column should match the labeled node
```

If you only have one node (e.g. a single-server k3d cluster), label the
agent node instead and confirm the pod schedules there rather than the
server node — or remove the label and watch the pod go `Pending` if no node
matches, then use `affinity.nodeAffinity` with `preferredDuringScheduling...`
instead of `requiredDuringScheduling...` to see the difference between a
hard and soft constraint.

## Cleanup when done with the module

```bash
kubectl delete -f statefulset.yaml -f daemonset.yaml -f job.yaml -f cronjob.yaml \
  -f resource-limits-deployment.yaml -f node-affinity-pod.yaml
kubectl label node <node-name> disktype-
```
