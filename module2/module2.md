# Module 2 — Configuration & State

Commands and manifests for each exercise in Module 2 of [../roadmap.md](../roadmap.md).

## 1. ConfigMap as environment variables

Create `configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  APP_COLOR: blue
  APP_MODE: development
```

Create `pod-env-configmap.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: config-env-pod
spec:
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
      envFrom:
        - configMapRef:
            name: app-config
```

```bash
kubectl apply -f configmap.yaml
kubectl apply -f pod-env-configmap.yaml
kubectl exec config-env-pod -- env | grep APP_
```

## 2. ConfigMap as a mounted volume

Create `pod-volume-configmap.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: config-volume-pod
spec:
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
      volumeMounts:
        - name: config-volume
          mountPath: /etc/config
  volumes:
    - name: config-volume
      configMap:
        name: app-config
```

```bash
kubectl apply -f pod-volume-configmap.yaml
kubectl exec config-volume-pod -- ls /etc/config
kubectl exec config-volume-pod -- cat /etc/config/APP_COLOR
```

Compare: env vars are fixed at pod start; a mounted ConfigMap volume updates
its files (with a short delay) if the ConfigMap changes, without restarting
the pod. Env vars do not.

## 3. Secret

Create `secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
type: Opaque
stringData:
  DB_PASSWORD: "sup3rsecret"
```

Create `pod-secret.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secret-env-pod
spec:
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
      envFrom:
        - secretRef:
            name: db-secret
```

```bash
kubectl apply -f secret.yaml
kubectl apply -f pod-secret.yaml
kubectl exec secret-env-pod -- env | grep DB_PASSWORD

# confirm it's only base64-encoded, not encrypted
kubectl get secret db-secret -o yaml
echo "<base64-value-from-above>" | base64 -d
```

Secrets are base64-encoded, not encrypted, in the default k3s datastore —
anyone with API access (or datastore access) can read them in plaintext.
Use RBAC to restrict access, and consider encryption-at-rest or an external
secrets manager for real credentials.

## 4. PersistentVolumeClaim with local-path

Check the default storage class (k3s ships with `local-path`):

```bash
kubectl get storageclass
```

Create `pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 1Gi
```

Create `pod-pvc.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: pvc-pod
spec:
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: data-pvc
```

```bash
kubectl apply -f pvc.yaml
kubectl apply -f pod-pvc.yaml
kubectl get pvc data-pvc

# write a file, delete the pod, recreate it, confirm the file survives
kubectl exec pvc-pod -- sh -c 'echo hello from pvc > /data/test.txt'
kubectl delete pod pvc-pod
kubectl apply -f pod-pvc.yaml
kubectl wait --for=condition=Ready pod/pvc-pod --timeout=60s
kubectl exec pvc-pod -- cat /data/test.txt
```

## Cleanup when done with the module

```bash
kubectl delete pod config-env-pod config-volume-pod secret-env-pod pvc-pod
kubectl delete pvc data-pvc
kubectl delete configmap app-config
kubectl delete secret db-secret
```
</content>
</invoke>
