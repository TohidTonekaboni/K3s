# Module 7 — Cluster Operations

Commands and manifests for each exercise in Module 7 of [../roadmap.md](../roadmap.md).

## 1. Checking version and performing an upgrade

```bash
kubectl get nodes -o wide   # VERSION column shows the k3s version per node
k3s --version 2>/dev/null || docker exec k3d-testcluster-server-0 k3s --version
```

Read the release notes for the next minor version before upgrading:
https://github.com/k3s-io/k3s/releases

On a disposable k3d cluster, the simplest "upgrade" is recreating the
cluster while pinning a specific k3s image tag:

```bash
k3d cluster create upgrade-test --image rancher/k3s:v1.31.5-k3s1
kubectl get nodes -o wide
k3d cluster delete upgrade-test
```

To upgrade an *existing* cluster in place, k3d re-images each node
container:

```bash
k3d node edit k3d-testcluster-server-0 --image rancher/k3s:v1.31.5-k3s1
kubectl get nodes -o wide   # confirm the new VERSION after it restarts
```

For real (non-k3d) k3s installs, the standard path is re-running the
install script with `INSTALL_K3S_VERSION` set, or using the
[system-upgrade-controller](https://github.com/rancher/system-upgrade-controller)
for rolling, in-cluster upgrades.

## 2. Backing up and restoring cluster state

k3d's default single-server cluster uses k3s's embedded **SQLite**
datastore, not etcd — etcd only kicks in with multiple server nodes or
`--cluster-init`. Check which one you're running:

```bash
docker exec k3d-testcluster-server-0 cat /etc/rancher/k3s/config.yaml 2>/dev/null
kubectl get pods -n kube-system | grep -i etcd   # empty on a single-server SQLite cluster
```

**SQLite backup** — just copy the datastore file out of the server
container:

```bash
docker exec k3d-testcluster-server-0 sh -c \
  "cp /var/lib/rancher/k3s/server/db/state.db /var/lib/rancher/k3s/server/db/state.db.bak"
docker cp k3d-testcluster-server-0:/var/lib/rancher/k3s/server/db/state.db.bak ./state.db.bak
```

To simulate a restore, stop k3s inside the container, replace the file,
and restart it:

```bash
docker exec k3d-testcluster-server-0 sh -c \
  "cp state.db.bak /var/lib/rancher/k3s/server/db/state.db" # inside the db dir
docker restart k3d-testcluster-server-0
```

**etcd backup** (if you're running a multi-server/HA cluster) uses k3s's
built-in snapshot command instead:

```bash
docker exec k3d-testcluster-server-0 k3s etcd-snapshot save --name pre-change-snapshot
docker exec k3d-testcluster-server-0 k3s etcd-snapshot list

# restore requires stopping the server and restarting with --cluster-reset
docker exec k3d-testcluster-server-0 k3s server \
  --cluster-reset --cluster-reset-restore-path=/var/lib/rancher/k3s/server/db/snapshots/pre-change-snapshot
```

## 3. Adding a second node and rescheduling work

```bash
k3d node create extra-agent --cluster testcluster --role agent
kubectl get nodes   # new node should show Ready
```

Cordon the original agent node so nothing new schedules there, then
drain it to force its pods onto the new node:

```bash
kubectl cordon k3d-testcluster-agent-0
kubectl get pods -o wide   # existing pods on agent-0 are undisturbed by cordon alone

kubectl drain k3d-testcluster-agent-0 --ignore-daemonsets --delete-emptydir-data
kubectl get pods -o wide   # pods now rescheduled onto extra-agent

kubectl uncordon k3d-testcluster-agent-0   # allow scheduling back once done
```

(For a non-k3d bare-metal/VM setup, the equivalent is running the k3s
install script with `K3S_URL=https://<server-ip>:6443` and
`K3S_TOKEN=<token>` on the new agent, where the token comes from
`/var/lib/rancher/k3s/server/node-token` on the server.)

## 4. Read-only RBAC for a ServiceAccount

Create `readonly-rbac.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: viewer
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: read-only
  namespace: default
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "configmaps"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: viewer-read-only
  namespace: default
subjects:
  - kind: ServiceAccount
    name: viewer
    namespace: default
roleRef:
  kind: Role
  name: read-only
  apiGroup: rbac.authorization.k8s.io
```

```bash
kubectl apply -f readonly-rbac.yaml

# allowed
kubectl auth can-i list pods --as=system:serviceaccount:default:viewer -n default
kubectl auth can-i get configmaps --as=system:serviceaccount:default:viewer -n default

# denied — no write verbs granted, and no access outside "default"
kubectl auth can-i delete pods --as=system:serviceaccount:default:viewer -n default
kubectl auth can-i list pods --as=system:serviceaccount:default:viewer -n kube-system
```

## 5. Running kube-bench

```bash
docker run --rm -v /etc:/etc:ro -v /var:/var:ro \
  --pid=host docker.io/aquasec/kube-bench:latest --config-dir /opt/kube-bench/cfg --benchmark cis-1.24
```

Against a k3d node from the host, run it directly inside the server
container instead so it sees the actual k3s config/binaries:

```bash
docker exec k3d-testcluster-server-0 sh -c \
  "wget -qO- https://raw.githubusercontent.com/aquasecurity/kube-bench/main/hack/install.sh | sh" 2>/dev/null
docker exec k3d-testcluster-server-0 kube-bench run --targets node,policies
```

Review at least 3 `[FAIL]` or `[WARN]` findings — common ones on k3s
concern kubelet anonymous auth, file permissions on kubeconfig/certs, and
whether the API server has `--anonymous-auth` explicitly disabled.

## Cleanup when done with the module

```bash
kubectl delete -f readonly-rbac.yaml
k3d node delete extra-agent --cluster testcluster
rm -f state.db.bak
```
