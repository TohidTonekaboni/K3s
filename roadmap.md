# Kubernetes Learning Roadmap (via k3s on macOS)

Goal: go from "k3s is installed" to comfortably operating a Kubernetes cluster —
deploying apps, managing storage/networking, and debugging real problems —
through hands-on exercises. Each module has objectives, exercises, and a
"done when" checkpoint. Work top to bottom; don't skip the checkpoints.

## Setup notes (macOS)

k3s is designed for Linux, so on macOS it typically runs inside a VM/container
(e.g. via `k3d`, `multipass`, `colima`, `lima`, or Docker Desktop). Confirm
your setup before starting:

```bash
k3d cluster create testcluster --servers 1 --agents 1 -p "80:80@loadbalancer" -p "443:443@loadbalancer"
kubectl get nodes
k3d cluster stop testcluster

kubectl get nodes -o wide
kubectl cluster-info
kubectl get pods -A
```

The `-p "80:80@loadbalancer" -p "443:443@loadbalancer"` flags map host ports
80/443 to the cluster's Traefik ingress (via the k3d serverlb container).
Without them, `curl http://localhost/...` can't reach ingress at all —
the ingress `ADDRESS` shown by `kubectl get ingress` is only the container's
internal Docker network IP, not reachable directly from macOS.

If `kubectl` isn't pointed at your k3s cluster yet, find the kubeconfig
(often `/etc/rancher/k3s/k3s.yaml` on the node, or exported by k3d/multipass)
and set `KUBECONFIG` or merge it into `~/.kube/config`.

---

## Module 1 — Core Concepts & First Deployment

**Objectives:** understand Pods, Deployments, Services; use `kubectl` for the
basics.

**Exercises:**
1. Run a single pod imperatively: `kubectl run nginx --image=nginx`. Inspect
   it with `kubectl describe pod nginx` and `kubectl logs nginx`.
2. Delete the pod, then create the same workload declaratively as a YAML
   manifest (`Deployment` with 1 replica). Apply with `kubectl apply -f`.
3. Scale the deployment to 3 replicas via `kubectl scale` and again by
   editing the YAML and re-applying. Observe the diff in behavior.
4. Expose the deployment with a `Service` of type `ClusterIP`, then
   `NodePort`. Access it with `curl` from your Mac.
5. Break something on purpose: set an invalid image tag, watch the pod go
   into `ImagePullBackOff`, and use `kubectl describe` / `kubectl get events`
   to diagnose it.

**Done when:** you can create, scale, expose, and debug a basic Deployment
without looking anything up.

---

## Module 2 — Configuration & State

**Objectives:** ConfigMaps, Secrets, environment variables, volumes.

**Exercises:**
1. Create a `ConfigMap` with a couple of key/value pairs and mount it into a
   pod as environment variables. Verify with `kubectl exec ... -- env`.
2. Create the same ConfigMap but mount it as a volume (files on disk).
   Compare the two approaches.
3. Create a `Secret` (e.g. a fake DB password), mount it as env vars, and
   confirm `kubectl get secret -o yaml` shows it base64-encoded (not
   plaintext-safe — discuss why Secrets alone aren't "secure").
4. Add a `PersistentVolumeClaim` using k3s's default `local-path` storage
   class. Write a file to the mounted path from inside a pod, delete the
   pod, recreate it, and confirm the file persists.

**Done when:** you understand the difference between ConfigMap/Secret/Volume
and when to use each, and have persisted data across pod restarts.

---

## Module 3 — Networking

**Objectives:** Services (ClusterIP/NodePort/LoadBalancer), DNS, Ingress.

**Exercises:**
1. Deploy two apps (e.g. a simple API and a frontend). Have the frontend
   call the API using Kubernetes DNS (`servicename.namespace.svc.cluster.local`).
2. Use `kubectl exec` into a debug pod (`kubectl run tmp --rm -it
   --image=busybox -- sh`) and `nslookup` a service to see DNS resolution
   in action.
3. k3s ships with Traefik as its default Ingress controller — deploy an
   `Ingress` resource routing `/app1` and `/app2` to two different services,
   and test with `curl`.
4. Try a `LoadBalancer` type Service — k3s includes ServiceLB (Klipper) by
   default, so it should get an external IP automatically. Compare it to
   NodePort.
5. Create two `Namespaces`, deploy the same app in both, and use a
   `NetworkPolicy` to block traffic between them (requires a CNI that
   supports NetworkPolicy — check what k3s uses by default, e.g. Flannel,
   and note its NetworkPolicy limitations).

**Done when:** you can explain how a request flows from Ingress → Service →
Pod, and can debug DNS/connectivity issues from inside the cluster.

---

## Module 4 — Workload Types & Scheduling

**Objectives:** StatefulSets, DaemonSets, Jobs/CronJobs, resource requests
and limits, node affinity.

**Exercises:**
1. Deploy a `StatefulSet` (e.g. a simple Redis or Postgres) and observe the
   stable pod naming (`app-0`, `app-1`) and per-pod PVCs.
2. Deploy a `DaemonSet` and confirm it runs one pod per node
   (`kubectl get nodes` vs `kubectl get pods -o wide`).
3. Create a `Job` that runs a one-off task to completion, then a `CronJob`
   that runs every minute. Watch it with `kubectl get jobs,cronjobs`.
4. Add `resources.requests` and `resources.limits` (CPU/memory) to a
   deployment. Intentionally set a memory limit too low and watch the pod
   get OOMKilled.
5. If you have multiple nodes (or simulate labels on one), use
   `nodeSelector` or `affinity` rules to pin a pod to a specific node.

**Done when:** you know which workload type fits which use case, and can
reason about resource requests/limits and their failure modes.

---

## Module 5 — Observability & Debugging

**Objectives:** logs, events, metrics, troubleshooting muscle memory.

**Exercises:**
1. Install `metrics-server` (often bundled or easy to add in k3s) and run
   `kubectl top nodes` / `kubectl top pods`.
2. Deploy a pod that crash-loops on purpose (e.g. `exit 1` in the command).
   Diagnose the `CrashLoopBackOff` using `kubectl logs --previous` and
   `kubectl describe`.
3. Simulate a stuck rollout: deploy a bad image version via
   `kubectl set image`, watch the rollout stall, then `kubectl rollout
   undo` back to the last good version.
4. Practice the "debug pod" pattern: use `kubectl debug` or an ephemeral
   container to inspect a running pod without modifying it.
5. Explore `kubectl get events --sort-by=.lastTimestamp -A` across the
   whole cluster to understand cluster-wide activity.

**Done when:** given a broken deployment, you can independently diagnose the
root cause in under 10 minutes using only `kubectl`.

---

## Module 6 — Packaging & GitOps-lite

**Objectives:** Helm, Kustomize, multi-environment configs.

**Exercises:**
1. Install Helm and deploy a public chart (e.g. `nginx` or `redis` from
   Bitnami) into your k3s cluster. Inspect what it created with `helm get
   manifest`.
2. Write your own minimal Helm chart for one of your Module 1–3 apps, with
   a `values.yaml` for image tag and replica count.
3. Use `Kustomize` (bundled with `kubectl`) to manage `base` +
   `overlays/dev` and `overlays/prod` variants of the same app (different
   replica counts/env vars).
4. (Optional) Set up a lightweight GitOps loop: point Argo CD or Flux at a
   git repo containing your manifests and watch it auto-sync changes.

**Done when:** you can package an app as a Helm chart and manage
dev/prod variants without duplicating YAML.

---

## Module 7 — Cluster Operations

**Objectives:** upgrades, backup/restore, multi-node basics, security.

**Exercises:**
1. Check your k3s version (`k3s --version`) and read the upgrade notes for
   the next minor version; perform an upgrade in a disposable
   cluster/VM.
2. Practice etcd/state backup: k3s uses embedded SQLite or etcd — find and
   back up the datastore, then simulate a restore.
3. If feasible, add a second node to your cluster (e.g. via a second VM
   with `k3s agent` joining via `K3S_URL`/`K3S_TOKEN`) and reschedule a
   workload onto it by cordoning the first node.
4. Create a `Role`/`RoleBinding` (RBAC) restricting a `ServiceAccount` to
   read-only access in one namespace; test it with `kubectl auth can-i`.
5. Run `kube-bench` or similar against your k3s cluster and review at least
   3 findings.

**Done when:** you're comfortable with cluster lifecycle tasks (upgrade,
backup, scaling nodes) and basic RBAC.

---

## Suggested pace

- Modules 1–2: 1 weekend
- Module 3: 1 weekend (networking is the trickiest conceptually)
- Modules 4–5: 1 weekend
- Modules 6–7: spread over 1–2 weeks, less urgent

## Tracking progress

Check off modules as you complete them:

- [ ] Module 1 — Core Concepts & First Deployment
- [ ] Module 2 — Configuration & State
- [ ] Module 3 — Networking
- [ ] Module 4 — Workload Types & Scheduling
- [ ] Module 5 — Observability & Debugging
- [ ] Module 6 — Packaging & GitOps-lite
- [ ] Module 7 — Cluster Operations
</content>
</invoke>
