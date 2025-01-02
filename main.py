import requests
import pandas as pd
from atlassian import Confluence
import io
import re
from flask import Flask, jsonify, redirect
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/update_feature_flags": {"origins": "https://.atlassian.net"}})


# Configuration
GITLAB_TOKEN = ""
PROJECT_ID_QA = "" # Replace with your ID
PROJECT_ID_UAT = ""
PROJECT_ID_PROD = ""
REPOSITORY_IDS = []  # Replace with your repo names
GITLAB_API_URL = "https://gitlab.com/api/v4"
CONFLUENCE_API_URL =  "https://.atlassian.net/wiki"
PAGE_ID =   # ID Confluence page
BASE_URL = "https://.atlassian.net/wiki"
SPACE_KEY = ""
CONFLUENCE_API_TOKEN = ""
EMAIL = ''
PAGE_TITLE = "Feature Flags"
TEAMS = ["Name"] # Replace with your Teams names
global_log = []

REPOSITORY_MAP = [
    ("prod", PROJECT_ID_PROD),
    ("qa", PROJECT_ID_QA),
    ("uat", PROJECT_ID_UAT),
]

headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
# response = requests.get(GITLAB_API_URL, headers=headers)

def add_to_log(message):
    """
    Adds a record to the global log.

    Args:
        message (str): The log message to be added.
    """
    with open("script.log", "a") as log_file:
        log_file.write(f"{message}\n")
    global global_log
    global_log.append(message)

def fetch_all_feature_flags(repo_id):
    """
    Fetches all feature flags for a given repository from the GitLab API.

    Args:
        repo_id (int): The ID of the GitLab repository.

    Returns:
        list: A list of feature flags retrieved from the repository.
    """
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    url = f"{GITLAB_API_URL}/projects/{repo_id}/feature_flags"
    all_flags = []
    page = 1
    per_page = 100

    while True:
        response = requests.get(url, headers=headers, params={"page": page, "per_page": per_page})
        if response.status_code != 200:
            add_to_log(f"Error fetching flags for repository '{repo_id}': HTTP {response.status_code}")
            break

        flags = response.json()
        if not flags:
            add_to_log(f"No more flags found for repository '{repo_id}' after page {page}.")
            break

        all_flags.extend(flags)
        add_to_log(f"Fetched {len(flags)} flags from repository '{repo_id}' on page {page}.")

        page += 1

    add_to_log(f"Total flags fetched for repository '{repo_id}': {len(all_flags)}.")
    return all_flags

def get_team_from_flag_name(flag_name):
    """
    Determines the team associated with a feature flag based on its name.

    Args:
        flag_name (str): The name of the feature flag.

    Returns:
        str or None: The name of the team if found, otherwise None.
    """
    # Split the flag name into words (converted to lowercase for comparison)
    words = re.findall(r'\w+', flag_name.lower())
    for team in TEAMS:
        if team.lower() in words:
            return team  # Return the team name if found
    return None

def merge_feature_flags():
    """
    Merges feature flags from multiple repositories into a consolidated structure.

    Returns:
        pd.DataFrame: A DataFrame containing all feature flags and their details.
    """
    all_flags = {}
    seen_flags = set()  # Track flags found in the current iteration

    # Iterate through each repository and fetch feature flags
    for repo_url, repo_id in REPOSITORY_MAP:
        add_to_log(f"Fetching feature flags for repository: {repo_url}")
        flags = fetch_all_feature_flags(repo_id)
        
        for flag in flags:
            flag_name = flag["name"]
            seen_flags.add(flag_name)

            if flag_name not in all_flags:  # Initialize new flag data
                team_name = get_team_from_flag_name(flag_name)
                created_by = flag.get("created_by", {}).get("name", "Unknown")
                owned_by = f"{created_by} ({team_name})" if team_name else created_by

                all_flags[flag_name] = {
                    "Feature toggle name": flag_name,
                    "Feature description": flag.get("description", ""),
                    "Owned by": owned_by,
                    "Status": set(),
                }

            # Extract scopes, strategies, and user_list
            scopes = flag.get("scopes", [])
            strategies = flag.get("strategies", [])
            user_list = strategies[0].get("user_list") if strategies else None

            strategies_data = [
                {
                    "id": strategy["id"],
                    "name": strategy["name"],
                    "parameters": strategy["parameters"],
                    "scopes": strategy.get("scopes", []),
                }
                for strategy in strategies
            ]

            # Add status with JSON object containing scopes, strategies, and user_list
            all_flags[flag_name][repo_url] = {
                "status": "Enabled" if flag["active"] else "Disabled",
                "details": {
                    "scopes": scopes,
                    "strategies": strategies_data,
                    "user_list": user_list,
                },
            }
            status = "Active" if flag["active"] else "Inactive"
            all_flags[flag_name]["Status"].add(status)

    # Handle deleted flags
    for flag_name in list(all_flags.keys()):
        if flag_name not in seen_flags:
            for repo_url, _ in REPOSITORY_MAP:
                all_flags[flag_name][repo_url] = {
                    "status": "Deleted",
                    "details": {
                        "scopes": "N/A",
                        "strategies": "N/A",
                        "user_list": "N/A",
                    },
                }
            all_flags[flag_name]["Status"] = "Deleted 🔴"
        else:
            statuses = all_flags[flag_name]["Status"]
            if "Active" in statuses:
                all_flags[flag_name]["Status"] = "In Use 🟢"
            elif "Inactive" in statuses:
                all_flags[flag_name]["Status"] = "Inactive ⚪"

    # Additional logic for retaining descriptions and ownership for deleted flags
    for flag_name in all_flags:
        if flag_name not in seen_flags:
            all_flags[flag_name]["Feature description"] = all_flags[flag_name].get("Feature description", "No description")
            all_flags[flag_name]["Owned by"] = all_flags[flag_name].get("Owned by", "Unknown")
            add_to_log(f"Retained data for deleted flag: {flag_name}")

    for flag_name in all_flags:
        owned_by = all_flags[flag_name]["Owned by"]
        owned_by = owned_by.replace("Unknown", "").strip()
        owned_by = " ".join(dict.fromkeys(owned_by.split()))
        all_flags[flag_name]["Owned by"] = owned_by

    # Transform data to DataFrame
    expanded_data = []
    for flag_name, flag_data in all_flags.items():
        row = {
            "Feature toggle name": flag_data["Feature toggle name"],
            "Feature description": flag_data["Feature description"],
            "Owned by": flag_data["Owned by"],
            "Status": flag_data["Status"],
        }
        for repo_url, status_info in flag_data.items():
            if isinstance(status_info, dict):  # Handle statuses with details
                row[f"{repo_url}"] = status_info  # JSON with status and details
        expanded_data.append(row)

    add_to_log(f"Completed merging of feature flags. Total flags processed: {len(expanded_data)}")
    return pd.DataFrame(expanded_data)

def fetch_existing_table_from_confluence(page_title):
    """
    Fetches an existing table from a Confluence page.

    Args:
        page_title (str): The title of the Confluence page to fetch.

    Returns:
        tuple: A tuple containing the page ID (str) and the first table (pd.DataFrame) if it exists, or (None, None) if the page or table is not found.
    """
    confluence = Confluence(url=CONFLUENCE_API_URL, username=EMAIL, password=CONFLUENCE_API_TOKEN)

    # Fetch the page by its title
    add_to_log(f"Attempting to fetch page with title: {page_title}")
    page = confluence.get_page_by_title(SPACE_KEY, page_title)

    if not page:
        add_to_log(f"Page with title '{page_title}' not found in space '{SPACE_KEY}'")
        return None, None

    # Extract the page ID and fetch the page content
    page_id = page["id"]
    add_to_log(f"Page found: ID {page_id}. Fetching content.")
    page_content = confluence.get_page_by_id(page_id, expand="body.storage")["body"]["storage"]["value"]

    # Parse tables from the page content
    add_to_log(f"Parsing tables from the content of page ID {page_id}")
    tables = pd.read_html(io.StringIO(page_content))

    # Log if no tables are found
    if not tables:
        add_to_log(f"No tables found on page ID {page_id}.")
        return page_id, None

    add_to_log(f"Table successfully fetched from page ID {page_id}")
    return (page_id, tables[0])  # Return the page ID and the first table

def update_table(existing_table, new_table):
    """
    Updates the existing table with new data from the new table.

    Both tables are expected to have "Feature toggle name" as a unique identifier.

    Args:
        existing_table (pd.DataFrame): The current table containing existing data.
        new_table (pd.DataFrame): The table with updated or new data.

    Returns:
        pd.DataFrame: A merged table where new or updated rows from the new table overwrite existing ones.
    """
    # Set "Feature toggle name" as the index for both tables to facilitate merging
    add_to_log("Setting 'Feature toggle name' as index for the existing table.")
    existing_table.set_index("Feature toggle name", inplace=True, drop=True)

    add_to_log("Setting 'Feature toggle name' as index for the new table.")
    new_table.set_index("Feature toggle name", inplace=True, drop=True)

    # Merge the new table into the existing table
    add_to_log("Merging new table data into the existing table.")
    merged_table = new_table.combine_first(existing_table).reset_index()

    add_to_log("Table merge completed successfully.")
    return merged_table

def upload_table_to_confluence(html_content, page_id=None):
    """
    Uploads an HTML table to Confluence by creating or updating a page.

    If a `page_id` is provided, the function updates the existing page.
    Otherwise, it creates a new page in the specified Confluence space.

    Args:
        html_content (str): The HTML content of the table to upload.
        page_id (str, optional): The ID of the Confluence page to update. If None, a new page will be created.

    Returns:
        None
    """
    add_to_log("Initializing Confluence API connection.")
    confluence = Confluence(url=CONFLUENCE_API_URL, username=EMAIL, password=CONFLUENCE_API_TOKEN)

    if page_id:
        add_to_log(f"Updating existing page with ID: {page_id}.")
        confluence.update_page(page_id=page_id, title=PAGE_TITLE, body=html_content)
        add_to_log(f"Page with ID {page_id} successfully updated.")
    else:
        add_to_log(f"Creating a new page titled '{PAGE_TITLE}' in space '{SPACE_KEY}'.")
        confluence.create_page(space=SPACE_KEY, title=PAGE_TITLE, body=html_content)
        add_to_log(f"New page titled '{PAGE_TITLE}' successfully created.")

def generate_html_with_icons_and_dropdown(table):
    """
    Generates an HTML table with status icons and expandable dropdowns for detailed information.

    Args:
        table (DataFrame): The input table containing feature flags and their details.

    Returns:
        str: The HTML representation of the table with icons and dropdowns.
    """
    # Mapping status values to their respective icons
    status_icons = {
        "Enabled": '<span style="color: green;">&#x2714;</span>',  # Green check mark
        "Disabled": '<span style="color: red;">&#x2716;</span>',   # Red cross
        "Not Available": '<span style="color: gray;">&#x25CB;</span>',  # Gray circle
        "Deleted": '<span style="color: orange;">&#x1F5D1;</span>',  # Orange trash bin
    }

    def should_show_dropdown(details):
        """
        Determines whether to show the dropdown for a given cell.
        
        Args:
            details (dict): The details object containing strategies and scopes.
        
        Returns:
            bool: True if dropdown should be shown, False otherwise.
        """
        strategies = details.get("strategies", [])
        if not strategies:  # Empty strategies
            return False
        
        for strategy in strategies:
            # Check if all strategies are "default" with "environment_scope = *"
            if strategy.get("name") != "default" or not all(
                scope.get("environment_scope") == "*" for scope in strategy.get("scopes", [])
            ):
                return True
        return False

    def format_cell(cell):
        """
        Formats the cell with status icons and dropdowns.
        """
        if not isinstance(cell, dict):
            # Return "Not Available" with gray icon if cell is not a dictionary
            return f'{status_icons["Not Available"]}'
        
        status = cell.get("status", "Not Available")
        icon = status_icons.get(status, status_icons["Not Available"])
        
        if should_show_dropdown(cell.get("details", {})):
            dropdown = (
                f'<ac:structured-macro ac:name="expand" ac:schema-version="1">'
                f'<ac:parameter ac:name="title" style="max-width: 200px;">Show scope</ac:parameter>'
                f'<ac:rich-text-body>'
                f'<pre style="max-width: 200px; overflow: scroll; font-family: monospace; white-space: pre-wrap; word-wrap: break-word; background: #f9f9f9; padding: 10px; border-radius: 4px; border: 1px solid #ddd;">'
                f'{format_details(cell.get("details", {}))}'
                f'</pre>'
                f'</ac:rich-text-body>'
                f'</ac:structured-macro>'
            )
            return icon + dropdown
        
        return f'{icon}'

    # Process statuses in the table
    table = table.copy()
    for column in table.columns:
        if column not in ["Feature toggle name", "Feature description", "Owned by", "Status"]:
            table[column] = table[column].map(format_cell)

    # Generate HTML for the table
    table_html = f"""
    <table style="width: 100%; border-collapse: collapse; font-size: 14px; font-family: Arial, sans-serif;">
        <thead>
            <tr>
                {''.join(f'<th style="border: 1px solid #ddd; padding: 10px; background-color: #f4f4f4;">{col}</th>' for col in table.columns)}
            </tr>
        </thead>
        <tbody>
            {''.join(
                '<tr>' +
                ''.join(f'<td style="border: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: top;">{format_user_ids(cell) if column == "userIds" else cell}</td>' for column, cell in zip(table.columns, row)) +
                '</tr>'
                for row in table.values
            )}
        </tbody>
    </table>
    """
    style = """
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
            font-family: Arial, sans-serif;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
            vertical-align: top;
        }
        th {
            background-color: #f4f4f4;
            color: #333;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f1f1f1;
        }
        pre {
            max-height: 200px;
            overflow-y: auto;
            font-family: monospace;
            white-space: pre-wrap;
            word-wrap: break-word;
            background: #f9f9f9;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
        }
    </style>
    """
    return style + table_html

def format_user_ids(user_ids):
    """
    Formats a list of user IDs into a string with each ID on a new line.

    Args:
        user_ids (list or any): The user IDs to format, expected to be a list.

    Returns:
        str: A formatted string with user IDs separated by line breaks, or a single ID as a string.
    """
    # Check if user_ids is a list
    if isinstance(user_ids, list):
        # Log the number of user IDs being formatted
        add_to_log(f"Formatting {len(user_ids)} user IDs.")
        return "<br>".join(map(str, user_ids))  # Join user IDs with line breaks
    # Log that a single user ID is being returned
    add_to_log(f"Returning single user ID: {user_ids}")
    return str(user_ids)  # Convert single ID to string

def format_details(details):
    """
    Formats a JSON-like structure (dictionary or list) into an HTML representation.

    Args:
        details (dict or list): The details to format, expected to be a dictionary or a list.

    Returns:
        str: A formatted HTML string representing the details.
    """
    
    def json_to_html(data, level=0):
        """
        Recursively converts a JSON object into HTML.

        Args:
            data (dict or list): The JSON data to convert.
            level (int): The current indentation level for nested structures.

        Returns:
            str: The HTML representation of the JSON data.
        """
        html = ""
        indent = "&nbsp;" * (level * 4)  # Create indentation for nested elements
        if isinstance(data, dict):
            for key, value in data.items():
                html += f"{indent}<strong>{key}:</strong> {json_to_html(value, level + 1)}<br>"
        elif isinstance(data, list):
            for item in data:
                html += f"{indent}- {json_to_html(item, level + 1)}<br>"
        else:
            html += f"{indent}{str(data)}"  # Convert non-dict/list data to string
        return html
    
    return json_to_html(details)  # Call the recursive function to convert details to HTML

def generate_log_html():
    """Generates HTML for log messages."""
    if not global_log:
        return "<div>No log messages available.</div>"
    
    log_html = "<div style='margin: 20px 0; padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;'>"
    log_html += "<strong>Stack trace:</strong><br>"
    for message in global_log:
        log_html += f"<div style='margin-bottom: 5px;'>{message}</div>"
    log_html += "</div>"
    
    return log_html

def add_link():
    return """
    <div style='margin: 20px 0; padding: 10px; text-align: center;'>
        <a href='http://localhost/update_feature_flags' style='
            display: inline-block;
            padding: 10px 20px; 
            font-size: 16px; 
            font-weight: bold; 
            color: white; 
            background-color: #0073e6; 
            text-decoration: none; 
            border-radius: 5px; 
            transition: background-color 0.3s ease, transform 0.2s ease;'
            onclick="event.preventDefault(); fetch('http://localhost/update_feature_flags', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            }).then(response => {
                if (response.ok) {
                    alert('Feature flags updated successfully!');
                } else {
                    alert('Error updating feature flags.');
                }
            });">
            Update Feature Flags
        </a>
    </div>
    """

@app.route('/update_feature_flags', methods=['GET'])
def update_feature_flags():
    try:
        add_to_log("Loading new feature flags...")
        new_table = merge_feature_flags()

        add_to_log("Checking existing table in Confluence...")
        page_id, existing_table = fetch_existing_table_from_confluence(PAGE_TITLE)

        if existing_table is None:
            add_to_log("Table not found. Creating a new one.")
            updated_table = new_table
        else:
            add_to_log("Updating existing table.")
            for _, row in existing_table.iterrows():
                flag_name = row["Feature toggle name"]
                if flag_name not in new_table["Feature toggle name"].values:
                    row["Status"] = "Deleted 🔴"
                    for repo_url, _ in REPOSITORY_MAP:
                        if repo_url not in row:
                            row[repo_url] = "Deleted"
                    new_table = pd.concat([new_table, pd.DataFrame([row])], ignore_index=True)

            updated_table = update_table(existing_table, new_table)

        add_to_log("Generating HTML code for the table...")
        html_content = updated_table.to_html(index=False, escape=False)

        add_to_log("Generating HTML code for the table with icons...")
        html_content = generate_html_with_icons_and_dropdown(updated_table)

        add_to_log("Uploading table to Confluence...")
        log_html = generate_log_html()
        html_button = add_link()
        html_content = html_button + html_content + log_html
        upload_table_to_confluence(html_content, page_id)

        add_to_log("Operation completed successfully!")
        return redirect('') # Replace with your Feature Flag page on confluence for redirect


    except Exception as e:
        add_to_log(f"Error occurred: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)  # Adjust host and port as needed
