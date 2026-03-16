#!/usr/bin/env python3
"""
Docker and SeaweedFS Filesystem Diagnostics Tool

Captures and compares filesystem usage snapshots for diagnosing disk space growth
in Docker overlay2 and SeaweedFS during Iris job processing.

Usage:
    python diagnose.py diagnose --output ./before
    # Run Iris jobs...
    python diagnose.py diagnose --output ./after
    python diagnose.py compare --before ./before --after ./after
"""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


VERSION = "1.0"


def run_command(cmd: List[str], input_text: Optional[str] = None) -> Tuple[bool, str, str]:
    """
    Run a subprocess command and return success status, stdout, and stderr.

    Args:
        cmd: Command as list of strings
        input_text: Optional stdin input

    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=input_text,
            timeout=60
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out after 60 seconds"
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, "", str(e)


def find_compose_file() -> Optional[Path]:
    """
    Find docker-compose.yml or compose.yaml in current directory.

    Returns:
        Path to compose file or None if not found
    """
    possible_names = [
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml"
    ]

    for name in possible_names:
        path = Path(name)
        if path.exists():
            return path

    return None


def prerequisites_check(seaweed_container: str, use_compose: bool) -> Dict[str, Any]:
    """
    Verify required tools and permissions are available.

    Args:
        seaweed_container: Name/service name of SeaweedFS container (pattern to match)
        use_compose: Whether to use docker compose exec

    Returns:
        Dict with check results, actual container name if found, and any warnings
    """
    checks = {
        "docker": False,
        "docker_accessible": False,
        "compose_file": None,
        "use_compose": use_compose,
        "seaweedfs_container": False,
        "seaweedfs_actual_name": None,  # The actual full container name
        "warnings": []
    }

    # Check docker command exists
    success, _, _ = run_command(["docker", "--version"])
    checks["docker"] = success
    if not success:
        checks["warnings"].append("Docker command not found")
        return checks

    # Check docker is accessible (not just installed)
    success, _, stderr = run_command(["docker", "ps"])
    checks["docker_accessible"] = success
    if not success:
        checks["warnings"].append(f"Cannot access Docker daemon: {stderr}")
        return checks

    # Check for compose file
    compose_file = find_compose_file()
    if compose_file:
        checks["compose_file"] = str(compose_file)
        if not use_compose:
            checks["warnings"].append(f"Found {compose_file} but not using 'docker compose exec' - consider using --compose flag")
    else:
        if use_compose:
            checks["warnings"].append("--compose flag used but no docker-compose.yml/compose.yaml found in current directory")
            return checks

    # Check SeaweedFS container/service exists and is running
    if use_compose:
        # Use docker compose ps to check service
        success, stdout, stderr = run_command(["docker", "compose", "ps", "--services", "--filter", "status=running"])
        if success and seaweed_container in stdout:
            checks["seaweedfs_container"] = True
            checks["seaweedfs_actual_name"] = seaweed_container  # In compose mode, use service name as-is
        else:
            checks["warnings"].append(f"SeaweedFS service '{seaweed_container}' not found in running compose services")
    else:
        # Use docker ps to find container by name pattern
        success, stdout, _ = run_command(["docker", "ps", "--format", "json"])
        if success:
            # Look for any running container with the pattern in its name
            matching_containers = []
            for line in stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    container = json.loads(line)
                    name = container.get("Names", "")
                    if seaweed_container in name:
                        matching_containers.append(name)
                except json.JSONDecodeError:
                    continue

            if matching_containers:
                checks["seaweedfs_container"] = True
                # Use the first match, but prefer exact match if available
                if seaweed_container in matching_containers:
                    checks["seaweedfs_actual_name"] = seaweed_container
                else:
                    checks["seaweedfs_actual_name"] = matching_containers[0]

                # Warn if multiple matches
                if len(matching_containers) > 1:
                    checks["warnings"].append(
                        f"Multiple containers match '{seaweed_container}': {', '.join(matching_containers)}. "
                        f"Using: {checks['seaweedfs_actual_name']}"
                    )
            else:
                checks["warnings"].append(f"No running container found matching pattern '{seaweed_container}'")
        else:
            checks["warnings"].append(f"Failed to list running containers")

    return checks


def capture_docker_system() -> Dict[str, Any]:
    """
    Capture output of 'docker system df' in JSON format.

    Returns:
        Parsed system df data or error dict
    """
    # Get summary in JSON format
    success, stdout_json, stderr = run_command(["docker", "system", "df", "--format", "json"])

    if not success:
        return {"error": stderr, "raw_output": ""}

    # Parse JSON lines
    summary = {}
    for line in stdout_json.strip().split('\n'):
        if not line:
            continue
        try:
            item = json.loads(line)
            type_name = item.get("Type", "").lower().replace(" ", "_")
            summary[type_name] = {
                "total": item.get("TotalCount"),
                "active": item.get("Active"),
                "size": item.get("Size"),
                "reclaimable": item.get("Reclaimable")
            }
        except json.JSONDecodeError:
            continue

    data = {
        "summary": summary,
        "raw_output": stdout_json
    }

    return data


def capture_docker_volumes() -> Dict[str, Any]:
    """
    Capture Docker volume information with sizes, filtered to volumes used by
    currently running containers. Each volume is annotated with the names of
    containers that mount it.

    Uses 'docker system df -v' to get volume sizes since 'docker volume ls'
    doesn't provide size information without sudo access to mountpoints.

    Returns:
        Dict with volume data
    """
    # Build volume → container-names mapping from running containers
    volume_to_containers: Dict[str, List[str]] = {}
    success_ps, stdout_ps, _ = run_command(["docker", "ps", "-q"])
    if success_ps and stdout_ps.strip():
        running_ids = [i for i in stdout_ps.strip().split('\n') if i]
        success_insp, stdout_insp, _ = run_command(["docker", "inspect"] + running_ids)
        if success_insp and stdout_insp.strip():
            try:
                inspect_list = json.loads(stdout_insp)
                for cdata in inspect_list:
                    cname = cdata.get("Name", "").lstrip("/")
                    for mount in cdata.get("Mounts", []):
                        if mount.get("Type") == "volume":
                            vol_name = mount.get("Name", "")
                            if vol_name:
                                volume_to_containers.setdefault(vol_name, [])
                                if cname not in volume_to_containers[vol_name]:
                                    volume_to_containers[vol_name].append(cname)
            except (json.JSONDecodeError, KeyError):
                pass

    # Get verbose output which includes volumes with sizes
    success, stdout, stderr = run_command(["docker", "system", "df", "-v"])

    if not success:
        return {
            "error": stderr,
            "volumes": {}
        }

    volumes = {}
    in_volumes_section = False

    for line in stdout.split('\n'):
        # Detect volumes section
        if "Local Volumes space usage" in line or "Volumes space usage" in line:
            in_volumes_section = True
            continue

        # Stop at next section
        if in_volumes_section and line.strip() and not line.startswith("VOLUME") and not any(c in line for c in [' ', '\t']) and line.strip() != "":
            # Empty line or new section
            if "Build Cache" in line or line.strip() == "":
                break

        # Parse volume lines
        if in_volumes_section and line.strip() and not line.startswith("VOLUME"):
            # Line format: VOLUME_NAME    LINKS     SIZE
            parts = line.split()
            if len(parts) >= 3:
                volume_name = parts[0]
                # Size is the last part
                size_str = parts[-1]

                # Skip header line
                if volume_name == "NAME" or size_str == "SIZE":
                    continue

                # Only include volumes used by currently running containers
                if volume_name not in volume_to_containers:
                    continue

                volumes[volume_name] = {
                    "name": volume_name,
                    "size": size_str,
                    "links": parts[1] if len(parts) > 1 else "0",
                    "containers": volume_to_containers[volume_name],
                }

    return {
        "volumes": volumes,
        "count": len(volumes)
    }


def capture_docker_containers() -> Dict[str, Any]:
    """
    Capture container information with sizes in JSON format.

    Returns:
        List of container data with writable layer sizes
    """
    # Get all containers with sizes in JSON format (--no-trunc to avoid path truncation)
    success, stdout, stderr = run_command(["docker", "ps", "-a", "--size", "--no-trunc", "--format", "json"])

    if not success:
        return {"error": stderr, "containers": []}

    containers = []
    for line in stdout.strip().split('\n'):
        if not line:
            continue
        try:
            container = json.loads(line)
            # Extract writable layer size from "Size" field
            # Format: "24.4kB (virtual 3.49GB)"
            size_str = container.get("Size", "0B")
            if " (virtual" in size_str:
                writable_size = size_str.split(" (virtual")[0].strip()
            else:
                writable_size = size_str
            container['WritableLayerSize'] = writable_size
            containers.append(container)
        except json.JSONDecodeError:
            continue

    return {"containers": containers}


def capture_overlay2_usage() -> Dict[str, Any]:
    """
    Capture overlay2 filesystem usage for all containers.
    Uses docker ps with --size to get writable layer sizes directly.

    Returns:
        Dict mapping container IDs to their overlay2 upper dir sizes
    """
    # Get all containers with sizes in JSON format (can't use -q with --format json)
    success, stdout, _ = run_command(["docker", "ps", "-a", "--size", "--format", "json"])

    if not success or not stdout.strip():
        return {"overlay2_dirs": {}}

    overlay_data = {}
    containers_data = []

    # Parse all container JSON first
    for line in stdout.strip().split('\n'):
        if not line:
            continue
        try:
            container = json.loads(line)
            containers_data.append(container)
        except json.JSONDecodeError:
            continue

    def get_overlay_info(container: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        cid = container.get("ID")
        if not cid:
            return None

        # Get UpperDir path using JSON format
        success, inspect_output, _ = run_command([
            "docker", "inspect", cid,
            "--format", "json"
        ])

        if not success or not inspect_output.strip():
            return None

        try:
            inspect_data = json.loads(inspect_output)
            if inspect_data and len(inspect_data) > 0:
                upper_dir_path = inspect_data[0].get("GraphDriver", {}).get("Data", {}).get("UpperDir")
            else:
                return None
        except (json.JSONDecodeError, IndexError, KeyError):
            return None

        # Extract writable layer size from container JSON
        size_str = container.get("Size", "0B")
        if " (virtual" in size_str:
            writable_size = size_str.split(" (virtual")[0].strip()
        else:
            writable_size = size_str

        return cid, {
            "upper_dir": upper_dir_path,
            "size": writable_size
        }

    # Parallel execution for efficiency
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_overlay_info, container) for container in containers_data]
        for future in as_completed(futures):
            result = future.result()
            if result:
                cid, data = result
                overlay_data[cid] = data

    return {"overlay2_dirs": overlay_data}


def capture_seaweedfs(container_name: str, use_compose: bool) -> Dict[str, Any]:
    """
    Capture SeaweedFS bucket usage via weed shell.

    Args:
        container_name: Name/service name of the SeaweedFS master container
        use_compose: Whether to use docker compose exec

    Returns:
        SeaweedFS bucket usage data or error dict
    """
    # Build command based on mode
    if use_compose:
        cmd = ["docker", "compose", "exec", "-T", container_name, "weed", "shell"]
    else:
        cmd = ["docker", "exec", "-i", container_name, "weed", "shell"]

    # Execute weed shell command
    success, stdout, stderr = run_command(
        cmd,
        input_text="fs.du /buckets\nexit\n"
    )

    if not success:
        return {
            "error": stderr,
            "raw_output": "",
            "buckets": {},
            "command_used": " ".join(cmd)
        }

    # Parse the output
    data = {
        "raw_output": stdout,
        "buckets": {},
        "command_used": " ".join(cmd)
    }

    # Simple parsing - look for bucket sizes
    # Output format varies, capture raw for now
    lines = stdout.strip().split('\n')
    for line in lines:
        # Look for lines with size information
        # Format typically: "directory: /buckets/xxx  size: 1234567"
        if 'size:' in line.lower():
            parts = line.split()
            for i, part in enumerate(parts):
                if part.lower() == 'size:' and i + 1 < len(parts):
                    # Extract bucket name from earlier in line
                    bucket_name = "unknown"
                    for p in parts[:i]:
                        if p.startswith('/buckets/'):
                            bucket_name = p
                            break
                    data["buckets"][bucket_name] = parts[i + 1]

    return data


def capture_disk_usage() -> Dict[str, Any]:
    """
    Capture disk usage information using df command.

    Returns:
        Dict with disk usage data per filesystem
    """
    # Get raw bytes using df with POSIX output
    success, stdout, stderr = run_command(["df", "-P", "-B1"])

    if not success:
        return {
            "error": stderr,
            "filesystems": {}
        }

    data = {
        "filesystems": {},
        "command_used": "df -P -B1"
    }

    # Parse df output
    # Header: Filesystem 1024-blocks Used Available Capacity Mounted on
    # With -B1: Filesystem 1-blocks Used Available Capacity Mounted on
    lines = stdout.strip().split('\n')

    for line in lines[1:]:  # Skip header
        parts = line.split()
        if len(parts) >= 6:
            filesystem = parts[0]
            total_bytes = int(parts[1])
            used_bytes = int(parts[2])
            available_bytes = int(parts[3])
            # parts[4] is capacity percentage
            mounted_on = " ".join(parts[5:])  # Mount point may have spaces

            data["filesystems"][mounted_on] = {
                "filesystem": filesystem,
                "total_bytes": total_bytes,
                "used_bytes": used_bytes,
                "available_bytes": available_bytes,
                "mounted_on": mounted_on
            }

    return data


def save_snapshot(data: Dict[str, Any], output_dir: Path) -> None:
    """
    Save diagnostic snapshot to JSON file.

    Args:
        data: Diagnostic data to save
        output_dir: Directory to save snapshot in
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_file = output_dir / "snapshot.json"

    with open(snapshot_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✓ Snapshot saved to {snapshot_file}")


def diagnose_command(args: argparse.Namespace) -> int:
    """
    Execute diagnose subcommand: capture system snapshot.

    Returns:
        Exit code (0 for success)
    """
    output_dir = Path(args.output)
    seaweed_pattern = args.container
    use_compose = args.compose

    # Auto-detect compose mode if not explicitly set
    if not use_compose:
        compose_file = find_compose_file()
        if compose_file:
            use_compose = True
            print(f"ℹ Auto-detected {compose_file}, using 'docker compose exec'")

    mode_str = "docker compose exec" if use_compose else "docker exec"
    print(f"Running diagnostics (SeaweedFS pattern: '{seaweed_pattern}', Mode: {mode_str})...")

    # Prerequisites check
    print("\n1. Checking prerequisites...")
    prereqs = prerequisites_check(seaweed_pattern, use_compose)

    if not prereqs["docker"]:
        print("✗ Docker not found")
        return 1
    print("✓ Docker found")

    if not prereqs["docker_accessible"]:
        print("✗ Cannot access Docker daemon")
        print(f"  Warnings: {', '.join(prereqs['warnings'])}")
        return 1
    print("✓ Docker accessible")

    if prereqs["compose_file"]:
        print(f"✓ Compose file found: {prereqs['compose_file']}")

    # Get the actual container name to use
    seaweed_container_name = prereqs.get("seaweedfs_actual_name")

    # Show warnings
    for warning in prereqs["warnings"]:
        if "not found" in warning.lower() or "not running" in warning.lower():
            continue  # Will handle below
        print(f"⚠ {warning}")

    if not prereqs["seaweedfs_container"]:
        entity = "service" if use_compose else "container"
        print(f"⚠ No SeaweedFS {entity} matching pattern '{seaweed_pattern}' found")
        print("  Will skip SeaweedFS diagnostics")
    else:
        entity = "service" if use_compose else "container"
        print(f"✓ SeaweedFS {entity} found: {seaweed_container_name}")

    # Capture diagnostics in parallel
    print("\n2. Capturing system diagnostics...")

    # Capture disk usage
    disk_data = capture_disk_usage()
    if "error" in disk_data:
        print(f"⚠ Disk usage capture failed: {disk_data['error']}")
    else:
        print(f"✓ Disk usage captured ({len(disk_data.get('filesystems', {}))} filesystems)")

    print("\n3. Capturing Docker diagnostics...")

    docker_data = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_system = executor.submit(capture_docker_system)
        future_containers = executor.submit(capture_docker_containers)
        future_overlay = executor.submit(capture_overlay2_usage)
        future_volumes = executor.submit(capture_docker_volumes)

        docker_data["system_df"] = future_system.result()
        docker_data["containers"] = future_containers.result()
        docker_data["overlay2"] = future_overlay.result()
        docker_data["volumes"] = future_volumes.result()

    volume_count = docker_data["volumes"].get("count", 0)
    print(f"✓ Docker diagnostics captured ({volume_count} volumes)")

    # Capture SeaweedFS if available
    seaweed_data = {}
    if prereqs["seaweedfs_container"] and seaweed_container_name:
        print("\n4. Capturing SeaweedFS diagnostics...")
        seaweed_data = capture_seaweedfs(seaweed_container_name, use_compose)
        if "error" in seaweed_data:
            print(f"⚠ SeaweedFS capture failed: {seaweed_data['error']}")
            print(f"  Command used: {seaweed_data.get('command_used', 'N/A')}")
        else:
            print("✓ SeaweedFS diagnostics captured")
    else:
        print("\n4. Skipping SeaweedFS diagnostics (service/container not available)")

    # Build snapshot
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "version": VERSION,
        "prerequisites": prereqs,
        "disk_usage": disk_data,
        "docker": docker_data,
        "seaweedfs": seaweed_data
    }

    # Save snapshot
    print(f"\n5. Saving snapshot to {output_dir}...")
    save_snapshot(snapshot, output_dir)

    print("\n✓ Diagnostics complete")
    return 0


def load_snapshot(snapshot_dir: Path) -> Dict[str, Any]:
    """
    Load a diagnostic snapshot from directory.

    Args:
        snapshot_dir: Directory containing snapshot.json

    Returns:
        Snapshot data
    """
    snapshot_file = snapshot_dir / "snapshot.json"

    if not snapshot_file.exists():
        raise FileNotFoundError(f"Snapshot file not found: {snapshot_file}")

    with open(snapshot_file, 'r') as f:
        return json.load(f)


def parse_size(size_str: str) -> int:
    """
    Parse size string (e.g., "1.2GB", "500MB", "1024") to bytes.

    Args:
        size_str: Size string with optional unit

    Returns:
        Size in bytes
    """
    if not size_str:
        return 0

    size_str = size_str.strip().upper()

    # Handle different unit formats
    multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4,
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
    }

    # Extract number and unit
    import re
    match = re.match(r'([0-9.]+)\s*([A-Z]*)', size_str)

    if not match:
        return 0

    number = float(match.group(1))
    unit = match.group(2) or 'B'

    return int(number * multipliers.get(unit, 1))


def format_size(bytes_val: int) -> str:
    """
    Format bytes as human-readable size.

    Args:
        bytes_val: Size in bytes

    Returns:
        Formatted string (e.g., "1.2 GB")
    """
    if bytes_val == 0:
        return "0 B"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0

    return f"{bytes_val:.2f} PB"


def calculate_deltas(before: Dict[str, Any], after: Dict[str, Any], threshold_percent: float = 10.0, threshold_bytes: int = 1024**3) -> Dict[str, Any]:
    """
    Calculate differences between two snapshots.

    Args:
        before: Before snapshot data
        after: After snapshot data
        threshold_percent: Percentage threshold for significant changes (default: 10.0)
        threshold_bytes: Byte threshold for significant changes (default: 1GB)

    Returns:
        Delta data with comparisons
    """
    deltas = {
        "before_timestamp": before.get("timestamp"),
        "after_timestamp": after.get("timestamp"),
        "docker": {},
        "seaweedfs": {},
        "significant_changes": []
    }

    # Compare Docker containers
    before_containers = before.get("docker", {}).get("containers", {}).get("containers", [])
    after_containers = after.get("docker", {}).get("containers", {}).get("containers", [])

    container_deltas = []
    for after_c in after_containers:
        cid = after_c.get("ID")
        name = after_c.get("Names", "unknown")

        # Find matching before container
        before_c = next((c for c in before_containers if c.get("ID") == cid), None)

        after_size = parse_size(after_c.get("WritableLayerSize", "0"))
        before_size = parse_size(before_c.get("WritableLayerSize", "0")) if before_c else 0

        delta_bytes = after_size - before_size

        if delta_bytes != 0:
            container_deltas.append({
                "id": cid,
                "name": name,
                "before": format_size(before_size),
                "after": format_size(after_size),
                "delta": format_size(delta_bytes),
                "delta_bytes": delta_bytes,
                "before_bytes": before_size
            })

    deltas["docker"]["containers"] = container_deltas

    # Compare overlay2 usage
    before_overlay = before.get("docker", {}).get("overlay2", {}).get("overlay2_dirs", {})
    after_overlay = after.get("docker", {}).get("overlay2", {}).get("overlay2_dirs", {})

    # Get all container IDs from both snapshots
    all_container_ids = set(list(before_overlay.keys()) + list(after_overlay.keys()))

    overlay_deltas = []
    for cid in all_container_ids:
        before_data = before_overlay.get(cid, {})
        after_data = after_overlay.get(cid, {})

        after_size = parse_size(after_data.get("size", "0") or "0")
        before_size = parse_size(before_data.get("size", "0") or "0")

        delta_bytes = after_size - before_size

        # Show all containers, even if delta is 0, if they have non-zero size
        # This helps track new containers that appeared
        if delta_bytes != 0 or after_size > 0 or before_size > 0:
            overlay_deltas.append({
                "container_id": cid,
                "before": format_size(before_size),
                "after": format_size(after_size),
                "delta": format_size(delta_bytes),
                "delta_bytes": delta_bytes,
                "before_bytes": before_size,
                "is_new": cid not in before_overlay,
                "is_removed": cid not in after_overlay
            })

    deltas["docker"]["overlay2"] = overlay_deltas

    # Compare Docker volumes (not bind mounts)
    before_volumes = before.get("docker", {}).get("volumes", {}).get("volumes", {})
    after_volumes = after.get("docker", {}).get("volumes", {}).get("volumes", {})

    all_volume_names = set(list(before_volumes.keys()) + list(after_volumes.keys()))

    volume_deltas = []
    for vol_name in all_volume_names:
        before_vol = before_volumes.get(vol_name, {})
        after_vol = after_volumes.get(vol_name, {})

        before_size = parse_size(before_vol.get("size", "0") if before_vol else "0")
        after_size = parse_size(after_vol.get("size", "0") if after_vol else "0")

        delta_bytes = after_size - before_size

        # Show volumes with changes or non-zero size
        if delta_bytes != 0 or after_size > 0 or before_size > 0:
            # Determine volume type (named vs anonymous)
            is_anonymous = len(vol_name) == 64 and all(c in '0123456789abcdef' for c in vol_name)
            volume_type = "anonymous" if is_anonymous else "named"

            # Prefer container names from the after snapshot; fall back to before
            containers = (after_vol or before_vol).get("containers", [])

            volume_deltas.append({
                "volume_name": vol_name,
                "volume_type": volume_type,
                "containers": containers,
                "before": format_size(before_size),
                "after": format_size(after_size),
                "delta": format_size(delta_bytes),
                "delta_bytes": delta_bytes,
                "before_bytes": before_size,
                "is_new": vol_name not in before_volumes,
                "is_removed": vol_name not in after_volumes
            })

    deltas["docker"]["volumes"] = volume_deltas

    # Compare SeaweedFS buckets
    before_buckets = before.get("seaweedfs", {}).get("buckets", {})
    after_buckets = after.get("seaweedfs", {}).get("buckets", {})

    bucket_deltas = []
    all_buckets = set(list(before_buckets.keys()) + list(after_buckets.keys()))

    for bucket in all_buckets:
        before_size = parse_size(before_buckets.get(bucket, "0"))
        after_size = parse_size(after_buckets.get(bucket, "0"))

        delta_bytes = after_size - before_size

        if delta_bytes != 0 or before_size > 0 or after_size > 0:
            bucket_deltas.append({
                "bucket": bucket,
                "before": format_size(before_size),
                "after": format_size(after_size),
                "delta": format_size(delta_bytes),
                "delta_bytes": delta_bytes,
                "before_bytes": before_size
            })

    deltas["seaweedfs"]["buckets"] = bucket_deltas

    # Compare disk usage
    before_disks = before.get("disk_usage", {}).get("filesystems", {})
    after_disks = after.get("disk_usage", {}).get("filesystems", {})

    disk_deltas = []
    all_mounts = set(list(before_disks.keys()) + list(after_disks.keys()))

    for mount in sorted(all_mounts):
        before_data = before_disks.get(mount, {})
        after_data = after_disks.get(mount, {})

        before_used = before_data.get("used_bytes", 0)
        after_used = after_data.get("used_bytes", 0)
        before_available = before_data.get("available_bytes", 0)
        after_available = after_data.get("available_bytes", 0)
        before_total = before_data.get("total_bytes", 0)
        after_total = after_data.get("total_bytes", 0)

        delta_used_bytes = after_used - before_used
        delta_available_bytes = after_available - before_available

        if delta_used_bytes != 0 or before_used > 0 or after_used > 0:
            disk_deltas.append({
                "mount_point": mount,
                "filesystem": after_data.get("filesystem", before_data.get("filesystem", "unknown")),
                "before_used": format_size(before_used),
                "after_used": format_size(after_used),
                "delta_used": format_size(delta_used_bytes),
                "delta_used_bytes": delta_used_bytes,
                "before_used_bytes": before_used,
                "before_available": format_size(before_available),
                "after_available": format_size(after_available),
                "delta_available": format_size(delta_available_bytes),
                "before_total": format_size(before_total),
                "after_total": format_size(after_total),
                "is_new": mount not in before_disks,
                "is_removed": mount not in after_disks
            })

    deltas["disk_usage"] = disk_deltas

    # Identify significant changes (>threshold_percent% or >threshold_bytes)
    threshold_percent_decimal = threshold_percent / 100.0

    for delta in container_deltas + overlay_deltas + volume_deltas + bucket_deltas + disk_deltas:
        delta_bytes = delta.get("delta_bytes") or delta.get("delta_used_bytes", 0)
        before_bytes = delta.get("before_bytes") or delta.get("before_used_bytes", 0)

        # Check absolute threshold (>= 1GB by default)
        if abs(delta_bytes) >= threshold_bytes:
            deltas["significant_changes"].append({
                "type": "absolute",
                "item": delta,
                "reason": f"Change >={format_size(threshold_bytes)}: {format_size(delta_bytes)}"
            })
        # Check percentage threshold (>= 10% by default)
        elif before_bytes > 0 and abs(delta_bytes / before_bytes) >= threshold_percent_decimal:
            percentage = (delta_bytes / before_bytes) * 100
            deltas["significant_changes"].append({
                "type": "percentage",
                "item": delta,
                "reason": f"Change >={threshold_percent}%: {percentage:.1f}% ({format_size(delta_bytes)})"
            })

    return deltas


def print_summary(deltas: Dict[str, Any], threshold_percent: float = 10.0, threshold_bytes: int = 1024**3) -> None:
    """
    Print human-readable summary of changes.

    Args:
        deltas: Delta data from calculate_deltas
        threshold_percent: Percentage threshold used for significant changes
        threshold_bytes: Byte threshold used for significant changes
    """
    print("\n" + "="*80)
    print("FILESYSTEM DIAGNOSTICS COMPARISON")
    print("="*80)

    print(f"\nBefore: {deltas['before_timestamp']}")
    print(f"After:  {deltas['after_timestamp']}")

    # Docker containers
    print("\n--- Docker Container Writable Layers ---")
    container_deltas = deltas["docker"].get("containers", [])

    if not container_deltas:
        print("No changes detected")
    else:
        print(f"\n{'Container':<30} {'Before':<15} {'After':<15} {'Delta':<15}")
        print("-" * 80)
        for item in sorted(container_deltas, key=lambda x: abs(x["delta_bytes"]), reverse=True):
            name = item["name"][:28]
            print(f"{name:<30} {item['before']:<15} {item['after']:<15} {item['delta']:<15}")

        total_delta = sum(item["delta_bytes"] for item in container_deltas)
        print("-" * 80)
        print(f"{'TOTAL':<30} {'':<15} {'':<15} {format_size(total_delta):<15}")

        # Show docker diff for containers with significant growth (> 1 MB)
        significant = [c for c in container_deltas if c["delta_bytes"] >= 1_000_000]
        if significant:
            print("\n--- Docker Diff (containers with > 1 MB growth) ---")
            for item in sorted(significant, key=lambda x: x["delta_bytes"], reverse=True):
                print(f"\n  $ docker diff {item['name']}  (+{item['delta']})")
                ok, stdout, stderr = run_command(["docker", "diff", item["name"]])
                if ok and stdout.strip():
                    for line in stdout.strip().split('\n'):
                        print(f"    {line}")
                elif stderr:
                    print(f"    (error: {stderr.strip()})")
                else:
                    print("    (no changes)")

    # Overlay2
    print("\n--- Docker Overlay2 Directories ---")
    overlay_deltas = deltas["docker"].get("overlay2", [])

    if not overlay_deltas:
        print("No changes detected")
    else:
        print(f"\n{'Container ID':<15} {'Status':<10} {'Before':<15} {'After':<15} {'Delta':<15}")
        print("-" * 85)
        for item in sorted(overlay_deltas, key=lambda x: abs(x["delta_bytes"]), reverse=True):
            cid = item["container_id"][:13]
            status = ""
            if item.get("is_new"):
                status = "[NEW]"
            elif item.get("is_removed"):
                status = "[REMOVED]"
            print(f"{cid:<15} {status:<10} {item['before']:<15} {item['after']:<15} {item['delta']:<15}")

        # Calculate and display total delta
        total_delta = sum(item["delta_bytes"] for item in overlay_deltas)
        new_count = sum(1 for item in overlay_deltas if item.get("is_new", False))
        removed_count = sum(1 for item in overlay_deltas if item.get("is_removed", False))
        changed_count = len(overlay_deltas) - new_count - removed_count

        print("-" * 85)
        status_summary = f"{new_count} new, {removed_count} removed" if (new_count or removed_count) else ""
        print(f"{'TOTAL':<15} {status_summary:<10} {'':<15} {'':<15} {format_size(total_delta):<15}")
        print(f"  ({len(overlay_deltas)} containers: {new_count} new, {changed_count} changed, {removed_count} removed)")

    # Docker volumes
    print("\n--- Docker Volumes (Named & Anonymous, running containers only) ---")
    volume_deltas = deltas["docker"].get("volumes", [])

    if not volume_deltas:
        print("No changes detected")
    else:
        print(f"\n{'Volume Name':<42} {'Container':<25} {'Type':<12} {'Before':<12} {'After':<12} {'Delta':<12}")
        print("-" * 115)
        for item in sorted(volume_deltas, key=lambda x: abs(x["delta_bytes"]), reverse=True):
            vol_name = item["volume_name"][:40]
            vol_type = item["volume_type"]
            container_str = ", ".join(item.get("containers", []))[:23]
            status = ""
            if item.get("is_new"):
                status = " [NEW]"
            elif item.get("is_removed"):
                status = " [REMOVED]"
            print(f"{vol_name:<42} {container_str:<25} {vol_type + status:<12} {item['before']:<12} {item['after']:<12} {item['delta']:<12}")

        # Calculate and display total delta
        total_delta = sum(item["delta_bytes"] for item in volume_deltas)
        new_count = sum(1 for item in volume_deltas if item.get("is_new", False))
        removed_count = sum(1 for item in volume_deltas if item.get("is_removed", False))
        changed_count = len(volume_deltas) - new_count - removed_count

        print("-" * 115)
        status_summary = f"{new_count} new, {removed_count} removed" if (new_count or removed_count) else ""
        print(f"{'TOTAL':<42} {status_summary:<25} {'':<12} {'':<12} {'':<12} {format_size(total_delta):<12}")
        print(f"  ({len(volume_deltas)} volumes: {new_count} new, {changed_count} changed, {removed_count} removed)")

    # SeaweedFS
    print("\n--- SeaweedFS Buckets ---")
    bucket_deltas = deltas["seaweedfs"].get("buckets", [])

    if not bucket_deltas:
        print("No changes detected")
    else:
        print(f"\n{'Bucket':<40} {'Before':<15} {'After':<15} {'Delta':<15}")
        print("-" * 80)
        for item in sorted(bucket_deltas, key=lambda x: abs(x["delta_bytes"]), reverse=True):
            bucket = item["bucket"][:38]
            print(f"{bucket:<40} {item['before']:<15} {item['after']:<15} {item['delta']:<15}")

        # Calculate and display total delta
        total_delta = sum(item["delta_bytes"] for item in bucket_deltas)
        print("-" * 80)
        print(f"{'TOTAL':<40} {'':<15} {'':<15} {format_size(total_delta):<15}")
        print(f"  ({len(bucket_deltas)} buckets tracked)")

    # Disk usage
    print("\n--- Disk Usage by Filesystem ---")
    disk_deltas = deltas.get("disk_usage", [])

    if not disk_deltas:
        print("No changes detected")
    else:
        print(f"\n{'Mount Point':<30} {'Filesystem':<20} {'Used Before':<15} {'Used After':<15} {'Delta Used':<15}")
        print("-" * 95)
        for item in sorted(disk_deltas, key=lambda x: abs(x.get("delta_used_bytes", 0)), reverse=True):
            mount = item["mount_point"][:28]
            fs = item["filesystem"][:18]
            status = ""
            if item.get("is_new"):
                mount = f"{mount} [NEW]"
            elif item.get("is_removed"):
                mount = f"{mount} [REMOVED]"
            print(f"{mount:<30} {fs:<20} {item['before_used']:<15} {item['after_used']:<15} {item['delta_used']:<15}")

        # Calculate and display total delta
        total_delta_used = sum(item.get("delta_used_bytes", 0) for item in disk_deltas)
        print("-" * 95)
        print(f"{'TOTAL':<30} {'':<20} {'':<15} {'':<15} {format_size(total_delta_used):<15}")
        print(f"  ({len(disk_deltas)} filesystems tracked)")

    # Significant changes
    print(f"\n--- Significant Changes (>={threshold_percent}% or >={format_size(threshold_bytes)}) ---")
    sig_changes = deltas.get("significant_changes", [])

    if not sig_changes:
        print("No significant changes detected")
    else:
        for change in sig_changes:
            print(f"⚠ {change['reason']}")
            print(f"  Item: {change['item']}")

    print("\n" + "="*80)


def save_comparison_json(deltas: Dict[str, Any], output_file: Path) -> None:
    """
    Save detailed comparison to JSON file.

    Args:
        deltas: Delta data
        output_file: Path to save JSON
    """
    with open(output_file, 'w') as f:
        json.dump(deltas, f, indent=2)

    print(f"\nDetailed comparison saved to: {output_file}")


def compare_command(args: argparse.Namespace) -> int:
    """
    Execute compare subcommand: compare two snapshots.

    Returns:
        Exit code (0 for success)
    """
    before_dir = Path(args.before)
    after_dir = Path(args.after)

    print(f"Loading snapshots...")
    print(f"  Before: {before_dir}")
    print(f"  After:  {after_dir}")

    try:
        before = load_snapshot(before_dir)
        after = load_snapshot(after_dir)
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"\n✗ Error parsing snapshot: {e}")
        return 1

    print("✓ Snapshots loaded")

    print("\nCalculating differences...")
    deltas = calculate_deltas(before, after, threshold_percent=args.threshold)
    print("✓ Differences calculated")

    # Print summary unless json-only mode
    if not args.json_only:
        print_summary(deltas, threshold_percent=args.threshold)

    # Save detailed JSON
    output_file = Path(args.output) if args.output else Path("comparison.json")
    save_comparison_json(deltas, output_file)

    return 0


def watch_command(args: argparse.Namespace) -> int:
    """
    Execute watch subcommand: run command with before/after diagnostics.

    Automatically captures diagnostics before running a command, executes it,
    captures diagnostics after, and compares results. Stores all data in tmpfs.

    Returns:
        Exit code (0 for success)
    """
    import tempfile
    from datetime import datetime

    # Create timestamped directory in tmpfs (/tmp)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    session_dir = Path(tempfile.gettempdir()) / f"diagnose-{timestamp}"
    session_dir.mkdir(parents=True, exist_ok=True)

    before_dir = session_dir / "before"
    after_dir = session_dir / "after"

    print("="*80)
    print("FILESYSTEM DIAGNOSTICS WATCH MODE")
    print("="*80)
    print(f"\nSession directory: {session_dir}")
    print(f"Command to execute: {' '.join(args.exec_command)}")
    print()

    # Step 1: Capture before snapshot
    print("Step 1/4: Capturing BEFORE snapshot...")
    print("-" * 80)

    # Create argparse.Namespace for diagnose_command
    diagnose_before_args = argparse.Namespace(
        output=str(before_dir),
        container=args.container,
        compose=args.compose
    )

    result = diagnose_command(diagnose_before_args)
    if result != 0:
        print(f"\n✗ Failed to capture before snapshot")
        print(f"Session files preserved at: {session_dir}")
        return result

    # Step 2: Execute the command
    print("\n" + "="*80)
    print("Step 2/4: Executing command...")
    print("-" * 80)

    # Join command for display and execution
    command_str = ' '.join(args.exec_command)
    print(f"Running: {command_str}\n")

    try:
        import time
        start_time = time.time()

        # Execute command with shell (to support shell built-ins like cd, pipes, etc.)
        result = subprocess.run(
            command_str,
            shell=True
        )

        elapsed = time.time() - start_time

        print(f"\n{'='*80}")
        print(f"Command finished (exit code: {result.returncode}, elapsed: {elapsed:.2f}s)")

        if result.returncode != 0:
            print(f"⚠ Command exited with non-zero status: {result.returncode}")
            if not args.continue_on_error:
                print(f"\nStopping diagnostics (use --continue-on-error to capture after snapshot anyway)")
                print(f"Session files preserved at: {session_dir}")
                return result.returncode
            print(f"Continuing with after snapshot due to --continue-on-error flag")

    except KeyboardInterrupt:
        print("\n\n✗ Command interrupted by user (Ctrl+C)")
        print(f"Session files preserved at: {session_dir}")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        print(f"\n✗ Error executing command: {e}")
        print(f"Session files preserved at: {session_dir}")
        return 1

    # Step 3: Capture after snapshot
    print("\n" + "="*80)
    print("Step 3/4: Capturing AFTER snapshot...")
    print("-" * 80)

    diagnose_after_args = argparse.Namespace(
        output=str(after_dir),
        container=args.container,
        compose=args.compose
    )

    result = diagnose_command(diagnose_after_args)
    if result != 0:
        print(f"\n✗ Failed to capture after snapshot")
        print(f"Session files preserved at: {session_dir}")
        return result

    # Step 4: Compare snapshots
    print("\n" + "="*80)
    print("Step 4/4: Comparing snapshots...")
    print("-" * 80)

    compare_args = argparse.Namespace(
        before=str(before_dir),
        after=str(after_dir),
        output=str(session_dir / "comparison.json"),
        json_only=False,
        threshold=args.threshold
    )

    result = compare_command(compare_args)

    # Cleanup or preserve files
    if args.keep_files:
        # Final summary - files preserved
        print("\n" + "="*80)
        print("WATCH SESSION COMPLETE")
        print("="*80)
        print(f"\nAll files saved to: {session_dir}")
        print(f"  - Before snapshot: {before_dir}/")
        print(f"  - After snapshot:  {after_dir}/")
        print(f"  - Comparison JSON: {session_dir}/comparison.json")
        print(f"\nTo re-run comparison with different threshold:")
        print(f"  {sys.argv[0]} compare --before {before_dir} --after {after_dir} --threshold 5.0")
        print()
    else:
        # Cleanup session directory
        import shutil
        print("\n" + "="*80)
        print("WATCH SESSION COMPLETE")
        print("="*80)
        try:
            shutil.rmtree(session_dir)
            print(f"\n✓ Session files cleaned up (use --keep-files to preserve)")
        except Exception as e:
            print(f"\n⚠ Warning: Could not clean up session directory: {e}")
            print(f"  Files at: {session_dir}")
        print()

    return result


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Docker and SeaweedFS filesystem diagnostics tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture before snapshot
  %(prog)s diagnose --output ./before

  # Capture after snapshot
  %(prog)s diagnose --output ./after

  # Compare snapshots
  %(prog)s compare --before ./before --after ./after

  # Watch a command (automatic before/after/compare)
  %(prog)s watch python script.py
  %(prog)s watch "bash -c 'for i in {1..10}; do ./run_job.sh; done'"
  %(prog)s watch "cd /app && python process.py --verbose"
  %(prog)s watch -- python script.py --flag value
  %(prog)s watch --keep-files python script.py  # Preserve session files
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Diagnose subcommand
    diagnose_parser = subparsers.add_parser(
        "diagnose",
        help="Capture filesystem diagnostics snapshot"
    )
    diagnose_parser.add_argument(
        "--output",
        required=True,
        help="Output directory for snapshot files"
    )
    diagnose_parser.add_argument(
        "--container",
        default="master",
        help="SeaweedFS container/service name pattern to match (default: master)"
    )
    diagnose_parser.add_argument(
        "--compose",
        action="store_true",
        help="Use 'docker compose exec' instead of 'docker exec' (auto-detected if compose file found)"
    )

    # Compare subcommand
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two diagnostic snapshots"
    )
    compare_parser.add_argument(
        "--before",
        required=True,
        help="Directory containing 'before' snapshot"
    )
    compare_parser.add_argument(
        "--after",
        required=True,
        help="Directory containing 'after' snapshot"
    )
    compare_parser.add_argument(
        "--output",
        help="Output file for detailed JSON comparison (default: comparison.json)"
    )
    compare_parser.add_argument(
        "--json-only",
        action="store_true",
        help="Skip human-readable summary, only save JSON"
    )
    compare_parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Threshold percentage for highlighting changes (default: 10.0)"
    )

    # Watch subcommand
    watch_parser = subparsers.add_parser(
        "watch",
        help="Run command with automatic before/after diagnostics and comparison"
    )
    watch_parser.add_argument(
        "exec_command",
        nargs="+",
        metavar="COMMAND",
        help="Command to execute (quote complex commands or use -- separator)"
    )
    watch_parser.add_argument(
        "--container",
        default="master",
        help="SeaweedFS container/service name pattern to match (default: master)"
    )
    watch_parser.add_argument(
        "--compose",
        action="store_true",
        help="Use 'docker compose exec' instead of 'docker exec' (auto-detected if compose file found)"
    )
    watch_parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Threshold percentage for highlighting changes (default: 10.0)"
    )
    watch_parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue with after snapshot even if command exits with error"
    )
    watch_parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep session files in /tmp after completion (default: auto-cleanup)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "diagnose":
        return diagnose_command(args)
    elif args.command == "compare":
        return compare_command(args)
    elif args.command == "watch":
        return watch_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
