#---------------------------------------------------------
# Default values
#---------------------------------------------------------
action = "create" # Options: create/delete. Defaults to create if not set
default_environment = "dev"

#---------------------------------------------------------
# Main script
#---------------------------------------------------------
import os, sys, io, argparse, time
import modules.fabric_cli_functions as fabcli
import modules.misc_functions as misc

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdout.reconfigure(line_buffering=True)

# Get arguments
parser = argparse.ArgumentParser(description="Fabric IaC setup arguments")
parser.add_argument("--environment", required=False, default=default_environment, help="Environment to setup. Default is dev.")
parser.add_argument("--action", required=False, default=action, help="Indicates the action to perform (Create/Delete). Default is Create.")
parser.add_argument("--tenant_id", required=False, default=os.environ.get('TENANT_ID'), help="Azure Active Directory (Microsoft Entra ID) tenant ID used for authenticating with Fabric APIs. Defaults to the TENANT_ID environment variable.")
parser.add_argument("--client_id", required=False, default=os.environ.get('CLIENT_ID'), help="Client ID of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_ID environment variable.")
parser.add_argument("--client_secret", required=False, default=os.environ.get('CLIENT_SECRET'), help="Client secret of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_SECRET environment variable.")
parser.add_argument("--github_pat", required=False, default=os.environ.get('GITHUB_PAT'), help="Github Personal Access Token. Used when source control provider is GitHub. Defaults to the FAB_GITHUB_PAT environment variable.")

args = parser.parse_args()
environment = args.environment
tenant_id = args.tenant_id
client_id = args.client_id
client_secret = args.client_secret
github_pat = args.github_pat
action = args.action.lower()

# Authenticate
fabcli.run_command("config set encryption_fallback_enabled true")
fabcli.run_command(f"auth login -u {client_id} -p {client_secret} --tenant {tenant_id}")

# Load JSON environment files (main and environment specific) and merge
main_json = misc.load_json(os.path.join(os.path.dirname(__file__), f'../resources/environments/infrastructure.json'))
env_json = misc.load_json(os.path.join(os.path.dirname(__file__), f'../resources/environments/infrastructure.{environment}.json'))
env_definition = misc.merge_json(main_json, env_json)

if action == "create":
    generic_connection_header_printed = False
    connection_permissions = env_definition.get("generic", {}).get("permissions")

    if (env_definition.get("generic").get("fabric_connections") and env_definition.get("generic").get("is_primary")):
        misc.print_header(f"Configuring generic solution connections") if not generic_connection_header_printed else None
        generic_connection_header_printed = True

        for connection in env_definition.get("generic").get("fabric_connections"):
            misc.print_info(f"Creating Fabric connection '{connection.get('name')}'...", bold=True, end="")
            fabric_connection = False
            if not fabcli.connection_exists(connection.get("name")):
                fabric_connection = fabcli.create_fabric_connection(
                    connection.get("name"),
                    connection.get("type"),
                    tenant_id,
                    client_id,
                    client_secret
                )
                if fabric_connection:
                    misc.print_success(" ✔")
                else: 
                    misc.print_error(f" ✖ Failed!")    
            else:
                misc.print_warning(" ⚠ Already exists")
                fabric_connection = fabcli.get_connection(connection.get('name'))

            if connection_permissions and fabric_connection:
                print(f"  • Assigning connection permissions...", end="")
                
                for permission, definitions in connection_permissions.items():
                    for definition in definitions:
                        role = "Owner" if permission == "Admin" else "User"
                        fabcli.add_connection_roleassignment(
                            fabric_connection.get("id"),
                            definition.get("id"),
                            definition.get("type"),
                            role
                            )
                misc.print_success(" ✔")


    git_settings = env_definition.get("generic").get("git_settings")
    git_connection = None
        
    if git_settings:
        misc.print_header(f"Configuring generic solution connections") if not generic_connection_header_printed else None
        generic_connection_header_printed = True
        misc.print_info(f"Creating source control connection '{git_settings.get("myGitCredentials").get("connection_name")}'", bold=True, end="")
        
        git_permissions = env_definition.get("generic", {}).get("permissions")
        connection_identifier = git_settings.get("myGitCredentials").get("connection_name") if git_settings.get("myGitCredentials").get("connection_name") else git_settings.get("myGitCredentials").get("connectionId")

        if fabcli.connection_exists(connection_identifier):
            git_connection = fabcli.get_connection(connection_identifier)
            misc.print_warning(f" ⚠ Already exists")
        else:           
            if git_settings.get('gitProviderDetails').get('gitProviderType').lower() == "github":
                repo_url = f"https://github.com/{git_settings.get('gitProviderDetails').get('ownerName')}/{git_settings.get('gitProviderDetails').get('repositoryName')}"
                fabcli.create_github_connection(git_settings.get("myGitCredentials").get("connection_name"), repo_url, github_pat)
                git_connection = fabcli.get_connection(connection_identifier)
            else:
                repo_url = f"https://dev.azure.com/{git_settings.get('gitProviderDetails').get('organizationName')}/{git_settings.get('gitProviderDetails').get('projectName')}/_git/{git_settings.get('gitProviderDetails').get('repositoryName')}"
                fabcli.create_azuredevops_connection(git_settings.get("myGitCredentials").get("connection_name"), repo_url, tenant_id, client_id, client_secret)
                git_connection = fabcli.get_connection(connection_identifier)
            
            misc.print_success(" ✔")

        if connection_permissions and git_connection:
            print(f"  • Assigning connection permissions...", end="")
            for permission, definitions in connection_permissions.items():
                for definition in definitions:
                    role = "Owner" if permission == "Admin" else "User"
                    fabcli.add_connection_roleassignment(
                        git_connection.get("id"),
                        definition.get("id"),
                        definition.get("type"),
                        role
                        )
            misc.print_success(" ✔")

    if env_definition:
        misc.print_header(f"Setting up {environment} environment")
        
        solution_name = env_definition.get("name")
        layers = env_definition.get("layers")
        default_capacity_name = env_definition.get("generic").get("capacity_name")
        
        has_item_connections = False
        for layer, layer_definition in layers.items():
            print("")
            workspace_name = solution_name.format(layer=layer, environment=environment)
            workspace_name_escaped = workspace_name.replace("/", "\\/")
            capacity_name = layer_definition.get("capacity_name", default_capacity_name)
            
            misc.print_info(f"Creating workspace '{workspace_name}'...", bold=True, end="")

            if fabcli.run_command(f"exists {workspace_name_escaped}.Workspace").replace("*", "").strip().lower() == "false":
                fabcli.run_command(f"create '{workspace_name_escaped}.Workspace' -P capacityname={capacity_name}")
                misc.print_success(" ✔", bold=True)
            else:
                misc.print_warning(f" ⚠ Already exists", bold=True)

            workspace_id = fabcli.run_command(f"get '{workspace_name_escaped}.Workspace' -q id").strip()
                
            # Update layer_definition
            layer_definition["workspace_id"] = workspace_id
            layer_definition["workspace_name"] = workspace_name
            
            permissions = layer_definition.get("permissions") or env_definition.get("generic", {}).get("permissions")

            if permissions:
                #misc.print_info(f"  • Assigning workspace permissions...", end="")
                for permission, definitions in permissions.items():
                    for definition in definitions:
                        misc.print_info(f"  • Assigning workspace permission for identity {definition.get('id')}...", end="")
                        fabcli.run_command(f"acl set {workspace_name_escaped}.Workspace -I {definition.get('id')} -R {permission.lower()} -f")
                        misc.print_success(" ✔")
                
            if (layer_definition.get("create_workspace_identity", False)):
                misc.print_info(f"  • Creating workspace identity...", end="")
                if fabcli.run_command(f"exists {workspace_name_escaped}.Workspace/.managedidentities/{workspace_name_escaped}.ManagedIdentity").replace("*", "").strip().lower() == "false":
                    fabcli.run_command(f"create {workspace_name_escaped}.Workspace/.managedidentities/{workspace_name_escaped}.ManagedIdentity")
                    misc.print_success(" ✔")
                else:
                    misc.print_warning(f" ⚠ Already exists", bold=True)      

            if layer_definition.get("items"):
                print_item_header = True
                for item_type, items in layer_definition.get("items").items():
                    for item in items:
                        if item.get("connection_name") and item_type in {"Lakehouse", "SQLDatabase"}:
                            has_item_connections = True

                        if not item.get("skip_item_creation", False):
                            if print_item_header:
                                print(f"  • Creating workspace items:") 
                                print_item_header = False

                            misc.print_info(f"    ◦ {item_type}: {item.get("item_name")}...", end="")

                            if not fabcli.item_exists(f'{workspace_name_escaped}.Workspace/{item.get("item_name")}.{item_type}'):    
                                fabcli.run_command(f"create '{workspace_name_escaped}.Workspace/{item.get("item_name")}.{item_type}'")
                                item["item_metadata"] = fabcli.get_item(f"/{workspace_name_escaped}.Workspace/{item.get('item_name')}.{item_type}", retry_count=2)
                                
                                if item_type in {"Lakehouse"}: 
                                    # Wait until SQL endpoint provisioning completes; treat missing metadata as still provisioning
                                    start_time = time.time()
                                    timeout_seconds = 60  # safety timeout
                                    while True:
                                        props = (item.get("item_metadata") or {}).get("properties") or {}
                                        sql_props = props.get("sqlEndpointProperties") or {}
                                        status = sql_props.get("provisioningStatus")
                                        if status and status != "InProgress":
                                            break
                                        if time.time() - start_time > timeout_seconds:
                                            misc.print_warning(" ⚠ Timed out waiting for Lakehouse SQL endpoint provisioning")
                                            break
                                        print(".", end="")
                                        time.sleep(2)
                                        item["item_metadata"] = fabcli.get_item(f"/{workspace_name_escaped}.Workspace/{item.get('item_name')}.{item_type}")

                                if item["item_metadata"]:                           
                                    misc.print_success(" ✔")
                                else:
                                    misc.print_error(" ✖ Failed!")
                            else:
                                item["item_metadata"] = fabcli.get_item(f"/{workspace_name_escaped}.Workspace/{item.get('item_name')}.{item_type}")
                                misc.print_warning(f" ⚠ Already exists")
  
            if layer_definition.get("private_endpoints"):
                print("  • Creating private endpoints:")
                for private_endpoint in layer_definition.get("private_endpoints"):
                    resource_type = misc.get_private_endpoint_resource_type(private_endpoint.get("id"))
                    print(f"    ◦ Provisioning {private_endpoint.get('name')}...", end="")

                    if (fabcli.item_exists(f"{workspace_name_escaped}.Workspace/.managedprivateendpoints/{private_endpoint.get('name')}.ManagedPrivateEndpoint")):
                        misc.print_warning(" ⚠ Already exists")
                    else:
                        try:
                            mpe_result = fabcli.run_command(
                                f'create {workspace_name_escaped}.Workspace/.managedprivateendpoints/'
                                f'{private_endpoint.get("name")}.ManagedPrivateEndpoint'
                                f' -P targetPrivateLinkResourceId={private_endpoint.get("id")},targetSubresourceType={resource_type},'
                                f'autoApproveEnabled=true' if private_endpoint.get("auto_approve") else 'autoApproveEnabled=false'
                            )
                            misc.print_success(" ✔")
                        except:
                            misc.print_error("  ✖ Failed!")

            git_settings = env_definition.get("generic").get("git_settings")
        
            if git_settings and git_connection:
                                
                if git_settings.get("myGitCredentials").get("connection_name"):
                    git_settings["myGitCredentials"].pop("connection_name", None) # Remove connection name
                    git_settings["myGitCredentials"]["connectionId"] = git_connection.get("id") # Add connection id instead

                if git_settings and layer_definition.get("git_directoryName"):
                    misc.print_info(f"  • Setting up Git integration...", end="")
                    git_settings = env_definition.get("generic").get("git_settings")
                    git_settings["gitProviderDetails"]["directoryName"] = layer_definition.get("git_directoryName")                    
                
                    if git_connection.get("id"):                   
                        connect_response = fabcli.connect_workspace_to_git(workspace_id, git_settings)
                        if connect_response:                            
                            init_response = fabcli.initialize_git_connection(workspace_id)
                            if init_response and init_response.get("requiredAction") != "None" and init_response.get("remoteCommitHash"):
                                fabcli.update_workspace_from_git(workspace_id, init_response.get("remoteCommitHash"))
                            
                            misc.print_success(" ✔")
                        else:
                            misc.print_error(f" ✖ Failed! Please verify connection and tenant settings.")
        
        if has_item_connections:
            misc.print_header(f"Configuring item connections")
            

            for layer, layer_definition in layers.items():
                workspace_name = solution_name.format(layer=layer, environment=environment)
                workspace_name_escaped = workspace_name.replace("/", "\\/")
                
                # Update layer_definition
                layer_definition["workspace_name"] = workspace_name

                if layer_definition.get("items"):
                    for item_type, items in layer_definition.get("items").items():
                        for item in items:

                            if item.get("connection_name") and item_type in {"Lakehouse", "SQLDatabase"}:
                                connection_name = item.get("connection_name").format(layer=layer, environment=environment)
                                item["item_metadata"] = fabcli.get_item(f"/{workspace_name_escaped}.Workspace/{item.get('item_name')}.{item_type}")
                                
                                misc.print_info(f"\nCreating item connection for {connection_name}...", bold=True, end="")

                                if item["item_metadata"]:
                                    server = (
                                        item.get("item_metadata").get("properties").get("sqlEndpointProperties").get("connectionString") if item_type == "Lakehouse" else
                                        item.get("item_metadata").get("properties").get("serverFqdn") 
                                    )

                                    database = (
                                        item.get("item_name") if item_type == "Lakehouse" else
                                        item.get("item_metadata").get("properties").get("databaseName") 
                                    )

                                    if not fabcli.connection_exists(connection_name):
                                        fabcli.create_sql_connection(connection_name, server, database, tenant_id, client_id, client_secret)
                                        misc.print_success(" ✔")
                                    else:
                                        misc.print_warning(" ⚠ Already exists")


                                    item["connection_metadata"] = fabcli.get_item(f".connections/{connection_name}.Connection")

                                    if permissions and fabcli.connection_exists(connection_name):
                                        print(f"  • Assigning connection permissions...", end="")
                                        for permission, definitions in permissions.items():
                                            for definition in definitions:
                                                role = "Owner" if permission == "Admin" else "User"
                                                fabcli.add_connection_roleassignment(
                                                    item.get("connection_metadata").get("id"), 
                                                    definition.get("id"),
                                                    definition.get("type"),
                                                    role
                                                    )
                                        misc.print_success(" ✔")
                                else:
                                    misc.print_error(" ✖ Failed to retrieve item!")
    else:
        misc.print_warning(f"No environment definition found for {environment}... Skipping setup!")

    print("")

elif action == "delete": 

    misc.print_header(f"Deleting generic solution connections")

    if (env_definition.get("generic").get("fabric_connections") and env_definition.get("generic").get("is_primary")):
        for connection in env_definition.get("generic").get("fabric_connections"):
            
            if fabcli.connection_exists(connection.get("name")):
                misc.print_info(f"Deleting connection '{connection.get('name')}'...", bold=True, end="")
                fabcli.run_command(f"rm .connections/{connection.get('name')}.Connection -f")
                misc.print_success(f" ✔")

    git_settings = env_definition.get("generic").get("git_settings")
    git_connection = None
        
    if git_settings:
        connection_identifier = git_settings.get("myGitCredentials").get("connection_name") if git_settings.get("myGitCredentials").get("connection_name") else git_settings.get("myGitCredentials").get("connectionId")
        if fabcli.connection_exists(connection_identifier):
            git_connection = fabcli.get_connection(connection_identifier)
            misc.print_info(f"Deleting connection '{git_connection.get("displayName")}'...", bold=True, end="")
            fabcli.run_command(f"rm .connections/{git_connection.get("displayName")}.Connection -f")
            misc.print_success(f" ✔")

    misc.print_header(f"Deleting {environment} environment")
    
    solution_name = env_definition.get("name")
    layers = env_definition.get("layers")
    default_capacityid = env_definition.get("generic").get("capacity_id")

    for layer, layer_definition in layers.items():
        workspace_name = solution_name.format(layer=layer, environment=environment)
        workspace_name_escaped = workspace_name.replace("/", "\\/")
        misc.print_info(f"Deleting workspace '{workspace_name}'...", bold=True, end="")
        if fabcli.run_command(f"exists {workspace_name_escaped}.Workspace").replace("*", "").strip().lower() == "true":

            if layer_definition.get("private_endpoints"):
                for private_endpoint in layer_definition.get("private_endpoints"):
                    if (fabcli.item_exists(f"{workspace_name_escaped}.Workspace/.managedprivateendpoints/{private_endpoint.get('name')}.ManagedPrivateEndpoint")):
                        fabcli.run_command(f"rm {workspace_name_escaped}.Workspace/.managedprivateendpoints/{private_endpoint.get('name')}.ManagedPrivateEndpoint -f")

            fabcli.run_command(f"rm '{workspace_name_escaped}.Workspace' -f")
            misc.print_success(" ✔")
        else:
            misc.print_warning(f" ⚠ Does not exist. Skipping deletion!")

        if layer_definition.get("items"):
            for item_type, items in layer_definition.get("items").items():
                for item in items:    
                    if item.get("connection_name") and item_type in {"Lakehouse", "SQLDatabase"}:
                        connection_name = item.get("connection_name").format(layer=layer, environment=environment)
                        misc.print_info(f"  • Deleting connection '{connection_name}'... ", bold=False, end="")
                        if fabcli.run_command(f"exists .connections/{connection_name}.Connection").replace("*", "").strip().lower() == "true":
                            fabcli.run_command(f"rm .connections/{connection_name}.Connection -f")
                            misc.print_success(" ✔")
                        else:
                            misc.print_warning(f" ⚠ Does not exist. Skipping deletion!")
else:
    misc.print_error(f"Invalid action specified: {action}. Supported values are Create/Delete.")