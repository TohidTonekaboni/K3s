# Capstone Project — FastAPI CI/CD with GitHub Actions, GitLab Runner & Argo CD on K3s

Goal: tie together everything from modules 1–7 into one end-to-end GitOps
pipeline — a real (small) FastAPI app, CI on GitHub Actions, CD driven by a
GitLab Runner registered on this laptop, and Argo CD pull-syncing the result
into the k3s cluster. Each phase below has objectives, exercises, and a
"done when" checkpoint, same as the modules in [../roadmap.md](../roadmap.md).
Work top to bottom.

## Architecture

```
GitHub repo (this repo, TohidTonekaboni/K3s)
  Capstone_Project/app/*              <- FastAPI source
  .github/workflows/capstone-ci.yml
    on push to main (paths: Capstone_Project/app/**, Dockerfile):
      1. pytest
      2. docker build & push -> ghcr.io/tohidtonekaboni/k3s-capstone-app:<sha>
      3. curl POST to GitLab pipeline trigger API, IMAGE_TAG=<sha>
              |
              v
GitLab repo (new, separate project: e.g. "k3s-capstone-gitops")
  k8s/namespace.yaml, deployment.yaml, service.yaml
  .gitlab-ci.yml
    triggered job runs on the LOCAL gitlab-runner (registered on this laptop):
      - bump the image tag in k8s/deployment.yaml
      - commit + push back to the repo
              |
              v
Argo CD (installed in k3s, namespace argocd)
  Application CR watches the GitLab repo's k8s/ path
  syncPolicy: automated (prune + selfHeal)
    -> detects the commit, syncs Deployment/Service into namespace "capstone"
```

Why two CI/CD systems instead of one: it mirrors a common real-world split
where application CI lives next to the app's source (GitHub) but deployment
config and its pipeline live in a separate, tightly-access-controlled GitOps
repo (GitLab), run by infra-owned runners rather than the app team's CI. It
also forces you to build the handoff between two different platforms, which
is the part most tutorials skip.

## Prerequisites

- GitHub repo: already have it (`git@github.com:TohidTonekaboni/K3s.git`)
- A GitLab account and the ability to create a project (gitlab.com is fine)
- Docker Desktop running locally
- k3s cluster reachable via `kubectl` (confirm with `kubectl get ns`)
- `brew` available for installing `gitlab-runner`

---

## Phase 1 — FastAPI application

**Objectives:** a small but real API to containerize and deploy — not a
"hello world" stub.

**Exercises:**
1. Scaffold `Capstone_Project/app/` with:
   - `main.py` — `GET /` (name/version), `GET /health` (liveness),
     `GET /items` and `POST /items` (simple in-memory list)
   - `requirements.txt` — `fastapi`, `uvicorn[standard]`, `pytest`, `httpx`
   - `tests/test_main.py` — use FastAPI's `TestClient` to hit all four
     endpoints, including one asserting a `POST /items` shows up in a
     subsequent `GET /items`
2. Run the app locally and hit it manually:
   ```bash
   cd Capstone_Project/app
   pip install -r requirements.txt
   uvicorn main:app --reload
   curl localhost:8000/health
   ```
3. Run the tests:
   ```bash
   pytest
   ```
4. Write `Capstone_Project/Dockerfile` (multi-stage not needed for something
   this small): base on `python:3.12-slim`, copy `app/`, `pip install`, run
   as a non-root user, `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`.
5. Build and run it:
   ```bash
   cd Capstone_Project
   docker build -t k3s-capstone-app .
   docker run --rm -p 8000:8000 k3s-capstone-app
   curl localhost:8000/health
   ```

**Done when:** `pytest` passes locally and the containerized app serves
`/health` with a 200 on `localhost:8000`.

---

## Phase 2 — GitHub Actions CI

**Objectives:** automated test + image build/push on every push to `main`.

**Exercises:**
1. Create a GHCR-compatible image name under your GitHub username, e.g.
   `ghcr.io/tohidtonekaboni/k3s-capstone-app`.
2. Write `.github/workflows/capstone-ci.yml`:
   - trigger on `push`/`pull_request`, scoped with
     `paths: ["Capstone_Project/app/**", "Capstone_Project/Dockerfile"]`
   - job `test`: checkout, `actions/setup-python`, `pip install -r requirements.txt`, `pytest`
   - job `build-and-push` (`needs: test`, `if: github.ref == 'refs/heads/main'`):
     `docker/login-action` against `ghcr.io` using `${{ github.actor }}` /
     `${{ secrets.GITHUB_TOKEN }}`, then `docker/build-push-action` tagging
     both `:${{ github.sha }}` and `:latest`
3. Push to `main` and watch the run in the GitHub Actions tab; confirm the
   new image appears under your GitHub profile's Packages tab.

**Done when:** pushing an app change produces a new image tag in GHCR
automatically, with no manual `docker push`.

---

## Phase 3 — GitLab GitOps repo + local GitLab Runner

**Objectives:** a separate repo holding only Kubernetes manifests, deployed
to by a runner registered on *this* laptop (not a shared GitLab SaaS runner).

**Exercises:**
1. Create a new GitLab project, e.g. `k3s-capstone-gitops` (gitlab.com,
   visibility private is fine).
2. Install and register a local runner:
   ```bash
   brew install gitlab-runner
   gitlab-runner register \
     --url https://gitlab.com/ \
     --registration-token <token-from-project-settings-ci-cd> \
     --executor docker \
     --docker-image alpine:latest \
     --description "laptop-runner"
   gitlab-runner run &   # or: brew services start gitlab-runner
   ```
3. In the new GitLab repo, add:
   - `k8s/namespace.yaml` — namespace `capstone`
   - `k8s/deployment.yaml` — Deployment referencing
     `ghcr.io/tohidtonekaboni/k3s-capstone-app:latest` (placeholder tag,
     gets bumped by the pipeline), 2 replicas, resource requests/limits
   - `k8s/service.yaml` — ClusterIP Service in front of it
4. Write `.gitlab-ci.yml`:
   - single job `bump-image`, `rules: - if: '$IMAGE_TAG'`, `tags: [laptop-runner]`
   - the job edits the image tag in `k8s/deployment.yaml` (`sed` or `yq`),
     then commits and pushes back to the repo using a project access token
     stored as a masked CI/CD variable (e.g. `GITOPS_PUSH_TOKEN`)
5. Test it manually before wiring up GitHub: in the GitLab UI, "Run
   pipeline" with variable `IMAGE_TAG=manual-test-1` and confirm a new
   commit appears in the repo, produced by your laptop's runner.

**Done when:** manually triggering the GitLab pipeline with an `IMAGE_TAG`
updates `k8s/deployment.yaml` via a commit made by the runner running on
this laptop.

---

## Phase 4 — Wiring GitHub CI → GitLab CD

**Objectives:** the cross-platform handoff — this is the part that makes it
a real two-system pipeline instead of two disconnected exercises.

**Exercises:**
1. In the GitLab project, create a pipeline trigger token
   (Settings → CI/CD → Pipeline triggers).
2. In the GitHub repo, add secrets: `GITLAB_TRIGGER_TOKEN` and
   `GITLAB_PROJECT_ID` (numeric project ID, found on the GitLab project's
   overview page).
3. Add a `trigger-cd` job to `capstone-ci.yml` (`needs: build-and-push`):
   ```bash
   curl -X POST \
     -F token=${{ secrets.GITLAB_TRIGGER_TOKEN }} \
     -F ref=main \
     -F "variables[IMAGE_TAG]=${{ github.sha }}" \
     https://gitlab.com/api/v4/projects/${{ secrets.GITLAB_PROJECT_ID }}/trigger/pipeline
   ```
4. Make a small change to `main.py`, push to `main`, and watch:
   GitHub Actions run → GitLab pipeline appears automatically → laptop
   runner picks it up → new commit lands in the GitLab repo — with zero
   manual steps.

**Done when:** one `git push` on GitHub produces, unattended, a new commit
in the GitLab manifests repo with the correct image tag.

---

## Phase 5 — Argo CD on K3s

**Objectives:** pull-based CD — the cluster reconciles itself against the
GitLab repo instead of anything pushing into it directly.

**Exercises:**
1. Install Argo CD:
   ```bash
   kubectl create namespace argocd
   kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   kubectl -n argocd wait --for=condition=available deploy --all --timeout=180s
   ```
2. Access the UI and log in:
   ```bash
   kubectl port-forward svc/argocd-server -n argocd 8080:443
   kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
   # https://localhost:8080, user: admin
   ```
3. Write `Capstone_Project/gitops-application.yaml` — an Argo CD
   `Application` CR: `repoURL` = the GitLab repo, `path: k8s`,
   `targetRevision: main`, `destination.namespace: capstone`,
   `syncPolicy.automated: {prune: true, selfHeal: true}`. Keep this file in
   the GitHub repo for reference even though Argo CD reads manifests from
   GitLab — it's the one resource that lives outside the GitOps loop itself.
4. Apply it and watch the sync:
   ```bash
   kubectl apply -f Capstone_Project/gitops-application.yaml
   kubectl get application -n argocd -w
   kubectl get pods -n capstone
   ```

**Done when:** `kubectl get application -n argocd` shows `Synced`/`Healthy`,
and `kubectl get pods -n capstone` shows the FastAPI deployment running.

---

## Phase 6 — Full round trip + failure drills

**Objectives:** prove the whole pipeline end to end, and understand what
each stage's failure looks like from the outside.

**Exercises:**
1. Change a response string in `main.py`, push to `main`, and time the full
   path: GitHub Actions → GitLab pipeline → Argo CD sync → new pod. Confirm
   with:
   ```bash
   kubectl port-forward -n capstone svc/<service-name> 8000:80
   curl localhost:8000/
   ```
2. Break each stage on purpose and observe how it surfaces:
   - a failing `pytest` — confirm `build-and-push` never runs
   - push a nonexistent image tag directly into `k8s/deployment.yaml` —
     confirm Argo CD reports the Application as `Degraded`/pods stuck in
     `ImagePullBackOff`
   - stop the local runner (`gitlab-runner stop`) and re-trigger from
     GitHub — confirm the GitLab pipeline sits `pending`
   - pause Argo CD auto-sync (`syncPolicy: {}` or "Disable Auto-Sync" in
     the UI) and push a manifest change — confirm the cluster does *not*
     update until you manually sync
3. Undo each induced failure and confirm the pipeline recovers.

**Done when:** you can narrate the full path from `git push` to a running
pod change from memory, and have seen and understood a failure at each of
the four stages (CI test, GitLab CD, runner, Argo CD sync).

---

## Cleanup when done

```bash
kubectl delete -f Capstone_Project/gitops-application.yaml
kubectl delete namespace capstone
kubectl delete namespace argocd
gitlab-runner unregister --all-runners
brew services stop gitlab-runner
```

## Tracking progress

- [x] Phase 1 — FastAPI application
- [ ] Phase 2 — GitHub Actions CI
- [ ] Phase 3 — GitLab GitOps repo + local runner
- [ ] Phase 4 — Wiring GitHub CI → GitLab CD
- [ ] Phase 5 — Argo CD on K3s
- [ ] Phase 6 — Full round trip + failure drills
