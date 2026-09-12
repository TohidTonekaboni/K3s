# Module 1 — Core Concepts & First Deployment

Commands and manifests for each exercise in Module 1 of [roadmap.md](roadmap.md).

## 1. Imperative pod

```bash
kubectl run nginx --image=nginx
kubectl get pods
kubectl describe pod nginx
kubectl logs nginx
kubectl delete pod nginx
```

## 2. Declarative Deployment

Create `module1-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nginx
          ports:
            - containerPort: 80
```

```bash
kubectl apply -f module1-deployment.yaml
kubectl get deployments
kubectl get pods -l app=nginx
```

## 3. Scaling

```bash
# imperative
kubectl scale deployment nginx-deployment --replicas=3
kubectl get pods -l app=nginx -w
```

Then edit `replicas: 3` in the YAML and re-apply:

```bash
kubectl apply -f module1-deployment.yaml
kubectl rollout status deployment/nginx-deployment
```

## 4. Expose with a Service

```bash
kubectl expose deployment nginx-deployment --name=nginx-clusterip --port=80 --target-port=80 --type=ClusterIP
kubectl get svc nginx-clusterip
```

Test from inside the cluster:

```bash
kubectl run tmp --rm -it --image=busybox --restart=Never -- wget -qO- nginx-clusterip
```

NodePort version:

```bash
kubectl expose deployment nginx-deployment --name=nginx-nodeport --port=80 --target-port=80 --type=NodePort
kubectl get svc nginx-nodeport
# note the assigned port under 80:XXXXX/TCP
curl http://localhost:<node-port>
```

If `curl localhost` doesn't reach it (depends on how your k3s VM networking is set up), get a node IP instead:

```bash
kubectl get nodes -o wide
curl http://<node-ip>:<node-port>
```

## 5. Break it on purpose

```bash
kubectl set image deployment/nginx-deployment nginx=nginx:this-tag-does-not-exist
kubectl get pods -l app=nginx
kubectl describe pod <pod-name>
kubectl get events --sort-by=.lastTimestamp
```

Fix it back:

```bash
kubectl set image deployment/nginx-deployment nginx=nginx
kubectl rollout status deployment/nginx-deployment
```

## Cleanup when done with the module

```bash
kubectl delete svc nginx-clusterip nginx-nodeport
kubectl delete deployment nginx-deployment
```
</content>
</invoke>
