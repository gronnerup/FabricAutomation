import os, argparse, json
import modules.fabric_cli_functions as fabcli
import modules.misc_functions as misc

default_branch_name = os.environ.get('GITHUB_REF_NAME') if os.environ.get('GITHUB_REF_NAME') else os.environ.get('BUILD_SOURCEBRANCH').removeprefix("refs/heads/")

# Get arguments 
parser = argparse.ArgumentParser(description="Fabric feature maintainance arguments")
parser.add_argument("--tenant_id", required=False, default=os.environ.get('FAB_TENANT_ID'), help="Azure Active Directory (Microsoft Entra ID) tenant ID used for authenticating with Fabric APIs. Defaults to the TENANT_ID environment variable.")
parser.add_argument("--client_id", required=False, default=os.environ.get('FAB_SPN_CLIENT_ID'), help="Client ID of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_ID environment variable.")
parser.add_argument("--client_secret", required=False, default=os.environ.get('FAB_SPN_CLIENT_SECRET'), help="Client secret of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_SECRET environment variable.")
parser.add_argument("--branch_name", required=False, default=default_branch_name, help="The name of the Git feature branch to operate on. Used for workspace setup, automation, and CI/CD logic. Defaults to a predefined variable `branch_name`.")
parser.add_argument("--action", required=False, default="create", help="Action to perform: `create` to set up a new feature branch and workspace,`delete` to clean up. Default is `create`.")

args = parser.parse_args()
tenant_id = args.tenant_id
client_id = args.client_id
client_secret = args.client_secret
branch_name = args.branch_name
action = args.action

feature_json = misc.load_json(os.path.join(os.path.dirname(__file__), f'../resources/environments/feature.json'))
layers = feature_json.get("layers")
permissions = feature_json.get("permissions")
capacity_name = feature_json.get("capacity_name")
feature_name = feature_json.get("feature_name")
git_settings = feature_json.get("git_settings")
branch_name_trimmed = branch_name.replace("feature/", "")

fabcli.run_command(f"auth login -u {client_id} -p {client_secret} --tenant {tenant_id}")

if action == "create":
    misc.print_header(f"Setting up feature development workspaces")
    for layer, layer_definition in layers.items():       
            workspace_name = feature_name.format(feature_name=branch_name_trimmed, layer_name=layer)
            workspace_name_escaped = workspace_name.replace("/", "\\/")
            if fabcli.run_command(f"exists {workspace_name_escaped}.Workspace").replace("*", "").strip().lower() == "false":
                misc.print_info(f"Creating workspace '{workspace_name}'... ", bold=True, end="")
                fabcli.run_command(f"create '{workspace_name_escaped}.Workspace' -P capacityname={capacity_name}")
                workspace_id = fabcli.run_command(f"get '{workspace_name_escaped}.Workspace' -q id").strip()
                misc.print_success("Done!", bold=True)

                if permissions:
                    misc.print_info(f"  - Assigning workspace permissions... ", end="")
                    for permission, definitions in permissions.items():
                        for definition in definitions:
                            fabcli.run_command(f"acl set '{workspace_name_escaped}.Workspace' -I {definition.get("id")} -R {permission.lower()} -f")
                    misc.print_success("Done!")

                if layer_definition.get("spark_settings"):
                    misc.print_info(f"  - Set workspace spark settings... ", end="")
                    spark_settings = misc.flatten_dict(layer_definition.get("spark_settings"))
                    for key, value in spark_settings:
                        fabcli.run_command(f"set '{workspace_name_escaped}.Workspace' -q sparkSettings.{key} -i {value} -f")
                    misc.print_success("Done!")

                if git_settings:
                    connection_id = None   
                    misc.print_info(f"  - Setting up Git integration ({git_settings.get('gitProviderDetails').get('gitProviderType')}) for workspace... ", end="")
                    
                    if git_settings.get("myGitCredentials").get("connectionId"):
                        if fabcli.connection_exists(git_settings.get("myGitCredentials").get("connectionId")):
                            connection_id = git_settings.get("myGitCredentials").get("connectionId")

                    if git_settings.get("myGitCredentials").get("connectionName"):
                        if git_settings.get('gitProviderDetails').get('gitProviderType').lower() == "github":
                            identity_username = os.environ.get('GITHUB_ACTOR')
                            identity_id =  os.environ.get("GITHUB_ACTOR_ID")
                        else:
                            identity_username = os.getenv("BUILD_REQUESTEDFOREMAIL").split("@")[0].upper()
                            identity_id = os.getenv("BUILD_REQUESTEDFORID")

                        connection_name = git_settings.get("myGitCredentials").get("connectionName").format(identity_id=identity_id, identity_username=identity_username)
                        
                        if fabcli.connection_exists(connection_name):
                            connection_id = fabcli.run_command(f"get .connections/{connection_name}.Connection -q id")
                            git_settings["myGitCredentials"].pop("connectionName", None) # Remove connection name
                            git_settings["myGitCredentials"]["connectionId"] = connection_id # Add connection id instead
                        else:
                            print("Connection does NOT exist")
                        
                    if connection_id:
                        git_settings["gitProviderDetails"]["branchName"] = branch_name
                        git_settings["gitProviderDetails"]["directoryName"] = layer_definition.get("git_directoryName")
                        
                        connect_response = fabcli.connect_workspace_to_git(workspace_id, git_settings)
                        if connect_response:                            
                            init_response = fabcli.initialize_git_connection(workspace_id)
                            if init_response and init_response.get("requiredAction") != "None" and init_response.get("remoteCommitHash"):
                                fabcli.update_workspace_from_git(workspace_id, init_response.get("remoteCommitHash"))
                            
                            misc.print_success("Done!")
                        else:
                            misc.print_error(f"Failed! Please verify connection and tenant settings.")
                    else:
                        misc.print_error(f"Connection not found. Skipping Git integration setup.")
                        
            else:
                misc.print_info(f"{workspace_name} already exist. Feature workspace creation skipped!", bold=True) 
            print ("")
    misc.print_success(f"Feature development workspace setup completed!",bold = True)
elif action == "delete":
    misc.print_header(f"Remove feature development workspaces")
    
    branch_name_trimmed = branch_name.removeprefix("refs/heads/feature/").removeprefix("feature/")
    
    for layer, layer_definition in layers.items():
        workspace_name = feature_name.format(feature_name=branch_name_trimmed, layer_name=layer)
        workspace_name_escaped = workspace_name.replace("/", "\\/")
        misc.print_info(f"Deleting workspace '{workspace_name}'... ", bold=True, end="")
        if fabcli.run_command(f"exists {workspace_name_escaped}.Workspace").replace("*", "").strip().lower() == "true":
            fabcli.run_command(f"rm '{workspace_name_escaped}.Workspace' -f")
            misc.print_success("Done!")
        else:
            misc.print_warning(f"Workspace does not exist. Skipping deletion!")

    misc.print_success(f"Removal of feature development workspaces completed!",bold = True)
else:
    misc.print_error(f"Unknown action '{action}'. Please use 'create', 'delete', or 'merge'.")
    exit(1)