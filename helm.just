SHOPTS := "set -euo pipefail"

OCI_IMAGE_REGISTRY := "quay.io"
OCI_IMAGE_ORG := "octopize"
OCI_REPO := OCI_IMAGE_REGISTRY / OCI_IMAGE_ORG

PATH_TO_CHART := "services-api-helm-chart"
RELEASE_NAME := "services-api"
NAMESPACE := "services-api"
PATH_TO_VALUES := PATH_TO_CHART / "values.yaml"

HELM_PACKAGE_DIR := "/tmp/helm-chart-builds"
OCI_IMAGE_NAME := "helm" + "/" + RELEASE_NAME

bootstrap: (install-yamllint)

install-yamllint:
    pip install yamllint

render: 
    just template {{PATH_TO_CHART}}

template *PATHS:
    @helm template {{RELEASE_NAME}} {{PATHS}} --namespace {{NAMESPACE}}

# Split the rendered output into individual yaml files
[private]
split-yaml:
    #!/usr/bin/env python
    import re
    import sys
    from pathlib import Path
    split_re = re.compile("^---$", re.MULTILINE)
    grab_source_re = re.compile("^# Source: (.+)$", re.MULTILINE)
    files_written = []
    for doc in re.split(split_re, sys.stdin.read()):

        source = grab_source_re.search(doc)
        filename = source.group(1) if source else None
        if not filename:
            continue

        # Discard the first line of the doc (Source)
        doc = "\n".join(doc.split("\n")[2:])

        new_file = Path('/tmp', filename)
        new_file.parent.mkdir(parents=True, exist_ok=True)
        files_written.append(new_file.as_posix())
        with open(new_file, "w") as f:
            f.write(doc)

    print(" ".join(files_written))

lint:
    #!/usr/bin/env bash
    {{SHOPTS}}
    # Verify helm syntax so that it can be installed
    helm lint {{PATH_TO_CHART}}

    # Verify consistency of yaml files
    rendered_output=$(just render)
    split_filenames=$(echo "$rendered_output" | just split-yaml)
    yamllint $split_filenames 

install:
    @helm install  \
        {{RELEASE_NAME}} \
        {{PATH_TO_CHART}} \
        --namespace {{NAMESPACE}} \
        --create-namespace \
        --values {{PATH_TO_VALUES}}

package:
    @helm package {{PATH_TO_CHART}} -d {{HELM_PACKAGE_DIR}}

# Push Helm Chart to quay.io
push-helm-chart:
    #!/usr/bin/env bash
    {{SHOPTS}}

    output=$(just package)
    # Extract out the name from 'Successfully packaged chart and saved it to: /tmp/helm-chart-builds/avatar-0.0.1.tgz'
    echo $output
    chart_file=$(echo "$output" | sed -n 's#\(.*saved it to: \)\(.*\)#\2#p')

    helm push "$chart_file" oci://{{OCI_REPO}}/{{OCI_IMAGE_NAME}}


login-helm-registry OCI_REPO_USERNAME OCI_PASSWORD:
    @helm registry login {{OCI_IMAGE_REGISTRY}} --username {{OCI_REPO_USERNAME}} --password {{OCI_PASSWORD}} 