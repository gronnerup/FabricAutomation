import subprocess, json, time

EXIT_ON_ERROR = True

def run_command(command: str) -> str:
    try:
        result = subprocess.run(
            ["fab", "-c", command],
            capture_output=True,
            text=True,
            check=EXIT_ON_ERROR
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running Fabric CLI command: {command}")
        print(e.stderr)
        if EXIT_ON_ERROR:
            raise
        return e.stderr.strip()
    

def connection_exists(connection_id):
    connection_url = f"connections/{connection_id}"
    response = run_command(f"api -X get {connection_url}")
    return json.loads(response).get("status_code", 404) == 200

def get_git_connection(workspace_id):
    git_url = f"workspaces/{workspace_id}/git/connection"
    
    retry_count = 0
    max_retries = 5
    while retry_count < max_retries:
        response = run_command(f"api -X get {git_url}")
        git_connectionstate = json.loads(response).get("text").get("gitConnectionState")
        if git_connectionstate == "NotConnected":
            # Connection not ready yet, wait and retry
            time.sleep(2)
            retry_count += 1
        else:
            return json.loads(response).get("text")
    
    return None  # Operation timed out or failed


def connect_workspace_to_git(workspace_id, git_settings):
    connect_url = f"workspaces/{workspace_id}/git/connect"
    run_command(f"api -X post {connect_url} -i {json.dumps(git_settings)}")
    git_connection = get_git_connection(workspace_id)
    return git_connection


def initialize_git_connection(workspace_id):
    initialize_url = f"workspaces/{workspace_id}/git/initializeConnection"
    post_data = {"initializationStrategy":"PreferRemote"}
    response = run_command(f"api -X post {initialize_url} -i {json.dumps(post_data)}")
    if json.loads(response).get("status_code") == 200:
        return json.loads(response).get("text")


def update_workspace_from_git(workspace_id, remote_commit_hash):
    update_url = f"workspaces/{workspace_id}/git/updateFromGit"

    post_data = {
        "remoteCommitHash": remote_commit_hash,
        "conflictResolution": {
            "conflictResolutionType": "Workspace",
            "conflictResolutionPolicy": "PreferWorkspace"
        },
        "options": {
            "allowOverrideItems": True
        }
    }

    response = json.loads(run_command(f"api -X post {update_url} -i {json.dumps(post_data)} --show_headers"))

    if response.get("status_code") == 202: #LRO
        operation_id = response.get("headers").get("x-ms-operation-id")
        poll_operation_status(operation_id)
    else:
        return response.get("text")

def poll_operation_status(operation_id):
    # Poll the operation status until it's done or failed
    retry_count = 0
    max_retries = 5
    while retry_count < max_retries:
        operation_url = f"operations/{operation_id}"
        operation_state = json.loads(run_command(f"api -X get {operation_url}"))
        state_status = operation_state.get("text").get("status")

        if state_status in ["NotStarted", "Running"]:
            time.sleep(2)
            retry_count += 1
        elif state_status == "Succeeded":
            return operation_state.get("text")
        else:
            return None
    
    return None  # Operation timed out or failed

    