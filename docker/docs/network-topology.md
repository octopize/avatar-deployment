# Docker Network Topology

## How to read this diagram

Each coloured box is a Docker **network** — think of it as a swimlane in a pool.
Containers in the same lane can reach each other by service name (Docker's internal DNS).
Containers in different lanes are completely isolated unless a service explicitly bridges them.

A service that spans multiple networks (e.g. `api`, `s3`) is placed in its **primary** network —
the one that best describes its role — but its arrows cross into other swimlanes to show every
connection it actually makes. This keeps the diagram readable without duplicating nodes.

Init/ephemeral containers (dashed border) run once at startup and exit; they are not part of
the steady-state topology.

```mermaid
flowchart LR
    classDef internet  fill:#263238,color:#fff,stroke:#37474f
    classDef proxy_svc fill:#1565c0,color:#fff,stroke:#0d47a1
    classDef compute   fill:#1b5e20,color:#fff,stroke:#2e7d32
    classDef pdf_svc   fill:#33691e,color:#fff,stroke:#558b2f
    classDef storage   fill:#bf360c,color:#fff,stroke:#e64a19
    classDef swfs      fill:#e65100,color:#fff,stroke:#ff6d00
    classDef db_svc    fill:#4a148c,color:#fff,stroke:#7b1fa2
    classDef auth_svc  fill:#880e4f,color:#fff,stroke:#ad1457
    classDef init_svc  fill:#424242,color:#fff,stroke:#616161,stroke-dasharray:4

    INTERNET(["🌐 Internet"]):::internet

    subgraph STACK["Avatar Stack"]

        subgraph proxy_net["proxy network"]
            nginx["nginx"]:::proxy_svc
            web["web"]:::proxy_svc
            api["api"]:::proxy_svc
            auth_server["authentik_server"]:::auth_svc
        end

        subgraph dask_net["dask network"]
            dask_sched["dask-scheduler"]:::compute
            dask_work["dask-worker"]:::compute
        end

        subgraph pdf_net["pdf network"]
            pdfgen["pdfgenerator"]:::pdf_svc
        end

        subgraph storage_net["storage network"]
            s3["s3"]:::storage
        end

        subgraph seaweedfs_net["seaweedfs network"]
            filer["filer"]:::swfs
            master["master"]:::swfs
            volume["volume"]:::swfs
            init_storage["init-storage"]:::init_svc
        end

        subgraph database_net["database network"]
            db[("db")]:::db_svc
            init_db["init-db"]:::init_svc
            auth_worker["authentik_worker"]:::auth_svc
            auth_init["authentik_init_db"]:::init_svc
        end

    end

    %% ── Published ports (external → host) ──────────────────────────
    INTERNET   ==":443/:80 published"==> nginx

    %% ── proxy network ───────────────────────────────────────────────
    nginx      -->|":3000"| web
    nginx      -->|":8000"| api
    nginx      -->|":9000 /sso"| auth_server
    nginx      -->|":8333 /storage"| s3

    %% ── dask network ────────────────────────────────────────────────
    api        -->|"dask scheduler"| dask_sched
    dask_sched -->|"dask worker"| dask_work

    %% ── pdf network ─────────────────────────────────────────────────
    dask_sched -->|"pdf jobs"| pdfgen
    dask_work  -->|"pdf jobs"| pdfgen

    %% ── storage network ─────────────────────────────────────────────
    api        -->|"S3 :8333"| s3
    dask_sched -->|"S3 :8333"| s3
    dask_work  -->|"S3 :8333"| s3
    init_db    -->|"S3 :8333"| s3
    init_storage -->|"S3 :8333"| s3

    %% ── seaweedfs network (internal) ────────────────────────────────
    s3         -->|":8888"| filer
    filer      -->|":9333"| master
    filer      -->|":8080"| volume

    %% ── database network ────────────────────────────────────────────
    api        -->|":5432"| db
    auth_server -->|":5432"| db
    auth_worker -->|":5432"| db
    init_db    -->|":5432"| db
    auth_init  -->|":5432"| db
```

## Key isolation properties

| Service | Networks | Notes |
|---|---|---|
| `nginx` | proxy, storage | Proxies `/storage` → `s3:8333` |
| `api` | proxy, dask, storage, database | Central hub |
| `authentik_server` | proxy, database | SSO — no storage access |
| `authentik_worker` | database | Applies blueprints via DB queue only |
| `s3` | storage, seaweedfs | Bridges client traffic and seaweedfs internals; binds `0.0.0.0` |
| `pdfgenerator` | pdf | No DB, no S3, no proxy access |
| `dask-scheduler` | dask, pdf, storage | Bridges compute and storage |
| `dask-worker` | dask, pdf, storage | Same as scheduler |
