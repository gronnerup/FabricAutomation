#---------------------------------------------------------
# Main script
#---------------------------------------------------------
import os, sys, io, argparse
import modules.fabric_cli_functions as fabcli
import modules.misc_functions as misc
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdout.reconfigure(line_buffering=True)

# Get arguments
parser = argparse.ArgumentParser(description="Fabric IaC setup arguments")
parser.add_argument("--environments", required=False, default="dev,tst,prd", help="Comma seperated list of environments to include in parameter file.")
parser.add_argument("--source_environment", required=False, default="dev", help="The source environment serving as source for the values being replaced.")
parser.add_argument("--tenant_id", required=False, default=os.environ.get('TENANT_ID'), help="Azure Active Directory (Microsoft Entra ID) tenant ID used for authenticating with Fabric APIs. Defaults to the TENANT_ID environment variable.")
parser.add_argument("--client_id", required=False, default=os.environ.get('CLIENT_ID'), help="Client ID of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_ID environment variable.")
parser.add_argument("--client_secret", required=False, default=os.environ.get('CLIENT_SECRET'), help="Client secret of the Azure AD application registered for accessing Fabric APIs. Defaults to the CLIENT_SECRET environment variable.")

args = parser.parse_args()
environments = args.environments.split(",")
source_environment = args.source_environment
tenant_id = args.tenant_id
client_id = args.client_id
client_secret = args.client_secret

# Authenticate
fabcli.run_command("config set encryption_fallback_enabled true")
fabcli.run_command(f"auth login -u {client_id} -p {client_secret} --tenant {tenant_id}")

data = {
    "environments": []
}

misc.print_header(f"Fetching environment details")

for environment in environments:    
    # Load JSON environment files (main and environment specific) and merge
    main_json = misc.load_json(os.path.join(os.path.dirname(__file__), f'../resources/environments/infrastructure.json'))
    env_json = misc.load_json(os.path.join(os.path.dirname(__file__), f'../resources/environments/infrastructure.{environment}.json'))
    env_definition = misc.merge_json(main_json, env_json)

    if env_definition:
        misc.print_info(f"Fetching details for {environment}...", bold=True, end="")
        
        solution_name = env_definition.get("name")
        layers = env_definition.get("layers")
        default_capacity_name = env_definition.get("generic").get("capacity_name")

        environment_definition = { "name": environment, "layers": [] }
        
        has_item_connections = False
        for layer_name, layer_definition in layers.items():
            workspace_name = solution_name.format(layer=layer_name, environment=environment)
            workspace_name_escaped = workspace_name.replace("/", "\\/")
            workspace_id = fabcli.run_command(f"get '{workspace_name_escaped}.Workspace' -q id").strip()
            print(f"Getting data for {workspace_id}, {workspace_name}")
            if(misc.is_guid(workspace_id)):
                workspace_items = fabcli.list_all_workspace_items(workspace_id)

                layer = {
                    "name": layer_name,
                    "workspace_name": workspace_name,
                    "workspace_id": workspace_id,
                    "items": []
                }
    
                # Get all items in the workspace
                for item in workspace_items:
                    fabric_item = {
                        "unique_name": f"{item.get('displayName')}.{item.get('type')}",
                        "name": item.get("displayName"),
                        "id": item.get("id"),
                        "type": item.get("type")
                    }

                    if item.get("type") in {"Lakehouse", "SQLDatabase"}:
                        item_details = fabcli.get_item(f"/{workspace_name_escaped}.Workspace/{item.get('displayName')}.{item.get('type')}", retry_count=2)
                        fabric_item.update({
                            "connectionString": item_details.get("properties").get("connectionString") if item.get("type") == "SQLDatabase" else item_details.get("properties").get("sqlEndpointProperties").get("connectionString") ,
                            "databaseName": item_details.get("properties").get("databaseName") if item.get("type") == "SQLDatabase" else None,
                            "serverFqdn": item_details.get("properties").get("serverFqdn") if item.get("type") == "SQLDatabase" else None,
                            "sqlEndpointId": item_details.get("properties").get("sqlEndpointProperties").get("id") if item.get("type") == "Lakehouse" else None,
                        })

                    layer["items"].append(fabric_item)

                # Get all layer connections
                if layer_definition.get("items"):
                    for item_type, items in layer_definition.get("items").items():
                        for item in items: 
                            if item.get("connection_name") and item_type in {"Lakehouse", "SQLDatabase"}:
                                connection_name = item.get("connection_name").format(layer=layer_name, environment=environment)
                                if fabcli.connection_exists(connection_name):
                                    connection = fabcli.get_item(f".connections/{connection_name}.Connection")
                                    upd_item = next((i for i in layer["items"] if i.get('unique_name') == f"{item.get('item_name')}.{item_type}"), None)
                                    if upd_item:
                                        upd_item['connectionId'] = connection.get("id")

                environment_definition["layers"].append(layer)
        
        data["environments"].append(environment_definition)
    else:
        misc.print_warning(f"No environment definition found for {environment}... Skipping!")

    print("")

print(f"DATA: {data}")

parameter_file_src = os.path.join(os.path.dirname(__file__), "../resources/parameters/parameter.yml")
yml_data = misc.build_parameter_yml(parameter_file_src, data)

# Copy the parameter file to each solution folder
solution_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../solution'))
for folder in os.listdir(solution_root):
    folder_path = os.path.join(solution_root, folder)
    if os.path.isdir(folder_path):
        dest_path = os.path.join(folder_path, 'parameter.yml')
        shutil.copyfile(parameter_file_src, dest_path)