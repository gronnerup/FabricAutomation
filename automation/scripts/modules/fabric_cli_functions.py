import subprocess, json, time, uuid

EXIT_ON_ERROR = False

def is_guid(value: str) -> bool:
    try:
        uuid_obj = uuid.UUID(value)
        return str(uuid_obj) == value.lower()
    except (ValueError, AttributeError, TypeError):
        return False

def run_command(command: str) -> str:
    try:
        result = subprocess.run(
            ["fab", "-c", command],
            capture_output=True,
            text=True,
            check=EXIT_ON_ERROR
        )
        output = result.stdout.strip()

        # Remove lines starting with ! (debug etc.)
        filtered_lines = [line for line in output.splitlines() if not line.strip().startswith("&#x27") and not line.strip().startswith("!")]
        clean_result = "\n".join(filtered_lines)
        return clean_result
    except subprocess.CalledProcessError as e:
        print(f"Error running Fabric CLI command: {command}")
        print(f"Error message: {e.stderr.strip()}")
        if EXIT_ON_ERROR:
            raise
        return e.stderr.strip()


def get_item(item_path: str, retry_count: int = 0):
    for attempt in range(retry_count + 1):
        try:
            return json.loads(run_command(f"get {item_path} -q ."))
        except Exception as e:
            if attempt < retry_count:
                time.sleep(2)
            else:
                return None


def get_connection(connection_identifier):
    if is_guid(connection_identifier): 
        connection_url = f"connections/{connection_identifier}"
        response = run_command(f"api -X get {connection_url} ")
        return json.loads(response)
    else:
        return json.loads(run_command(f"get .connections/{connection_identifier}.Connection -q ."))


def connection_exists(connection_identifier):
    if is_guid(connection_identifier): 
        connection_url = f"connections/{connection_identifier}"
        response = run_command(f"api -X get {connection_url}")
        return json.loads(response).get("status_code", 404) == 200
    else:
        return True if run_command(f"exists .connections/{connection_identifier}.Connection").replace("*", "").strip().lower() == "true" else False


def item_exists(item_path):
    return True if run_command(f"exists {item_path}").replace("*", "").strip().lower() == "true" else False


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
    response = run_command(f"api -X post {initialize_url}")
    if json.loads(response).get("status_code") == 200:
        return json.loads(response).get("text")


def get_git_status(workspace_id):
    status_url = f"workspaces/{workspace_id}/git/status"
    response = run_command(f"api -X get {status_url}")
    if json.loads(response).get("status_code") == 200:
        return json.loads(response).get("text")
    

def create_sql_connection(connection_name, server, database, tenant_id, client_id, client_secret):
    run_command(
        f"create .connections/{connection_name}.Connection -P "
        f"privacyLevel=Organizational,connectionDetails.type=SQL,connectionDetails.creationMethod=SQL,"
        f"credentialDetails.connectionEncryption=Encrypted,credentialDetails.type=ServicePrincipal,"
        f"connectionDetails.parameters.server={server},"
        f"connectionDetails.parameters.database={database},"
        f"credentialDetails.tenantId={tenant_id},"
        f"credentialDetails.servicePrincipalClientId={client_id},"
        f"credentialDetails.servicePrincipalSecret={client_secret}")


def create_azuredevops_connection(connection_name, repo_url, tenant_id, client_id, client_secret):
    run_command(
        f"create .connections/{connection_name}.Connection -P "
        f"privacyLevel=Organizational,connectionDetails.type=AzureDevOpsSourceControl,connectionDetails.creationMethod=AzureDevOpsSourceControl.Contents,"
        f"credentialDetails.connectionEncryption=NotEncrypted,credentialDetails.type=ServicePrincipal,"
        f"connectionDetails.parameters.url={repo_url},"
        f"credentialDetails.tenantId={tenant_id},"
        f"credentialDetails.servicePrincipalClientId={client_id},"
        f"credentialDetails.servicePrincipalSecret={client_secret}")
    

def create_github_connection(connection_name, repo_url, github_pat):
    command = (f"create .connections/{connection_name}.Connection -P "
        f"privacyLevel=Organizational,connectionDetails.type=GitHubSourceControl,connectionDetails.creationMethod=GitHubSourceControl.Contents,"
        f"credentialDetails.connectionEncryption=Encrypted,credentialDetails.type=Key,"
        f"connectionDetails.parameters.url={repo_url},"
        f"credentialDetails.key={github_pat}")
    run_command(command)


def create_fabric_connection(connection_name, connection_type, tenant_id, client_id, client_secret):
    creation_method = None
    
    match connection_type:
        case "FabricSql":
            creation_method = "FabricSql.Contents"
        case "FabricDataPipelines":
            creation_method = "FabricDataPipelines.Actions"
        case "Warehouse":
            creation_method = "Fabric.Warehouse" 

    timestamp_str = str(int(time.time()))
    if creation_method:
        max_retries = 10
        for attempt in range(1, max_retries + 1):
            try:
                test = run_command(
                    f"create .connections/{connection_name}.Connection -P "
                    f"privacyLevel=Organizational,connectionDetails.type={connection_type},connectionDetails.creationMethod={creation_method},"
                    f"connectionDetails.parameters.options={timestamp_str},"
                    f"credentialDetails.connectionEncryption=NotEncrypted,credentialDetails.type=ServicePrincipal,"
                    f"credentialDetails.tenantId={tenant_id},"
                    f"credentialDetails.servicePrincipalClientId={client_id},"
                    f"credentialDetails.servicePrincipalSecret={client_secret}")

                fabric_connection = get_connection(connection_name)

                if not fabric_connection:
                    raise Exception("Connection lookup returned no result.")

                return fabric_connection

            except Exception as e:
                print(f"...", end="")
                if attempt == max_retries:
                    return None
                time.sleep(5) # Wait before retrying 
        return 
    else:
        print(f"Connection type '{connection_type}' not supported!.")
        return None


def add_connection_roleassignment(connection_id, identity_id, identity_type, role):
    body = {
        "principal": {
            "id": identity_id,
            "type": identity_type
        },
        "role": role
    }

    response = run_command(f"api -X post connections/{connection_id}/roleAssignments -i {json.dumps(body)}")
    return json.loads(response)


def list_all_workspace_items(workspace_id):
    all_items = []
    continuation_token = None

    if is_guid(workspace_id):
        while True:
            command = f"workspaces/{workspace_id}/items"
            if continuation_token:
                command += f"?continuationToken={continuation_token}"

            response = run_command(f"api -X get {command}")
            data = json.loads(response)
            all_items.extend(data.get("text").get("value", []))
            continuation_token = data.get("continuationToken")
            if not continuation_token:
                break

    return all_items


def update_workspace_from_git(workspace_id, remote_commit_hash):
    update_url = f"workspaces/{workspace_id}/git/updateFromGit"

    post_data = {
        "remoteCommitHash": remote_commit_hash,
        "conflictResolution": {
            "conflictResolutionType": "Workspace",
            "conflictResolutionPolicy": "PreferRemote"
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